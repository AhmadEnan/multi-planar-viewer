# serialization/loader.py
# This file is part of the Multi-Planar Viewer project.
# It is responsible for loading serialized data.

import os
import numpy as np
import nibabel as nib
import pydicom
from pydicom.dataset import FileDataset
from typing import Optional, Dict, Any, Union, List
from pathlib import Path
import dicom2nifti
import tempfile


class DataLoader:
    """
    Medical images loader.
    This class handles loading of serialized medical image data.

    returns the data in a unified format (regardless of the type of the input file).
    The returned dictionary has the following structure:
    {
        "image": np.ndarray,          # 3D (or 4D) volume [Z, Y, X]
        "voxel_spacing": tuple,       # (dx, dy, dz)
        "orientation": np.ndarray,    # 4x4 affine (if available)
        "metadata": dict,             # Patient & acquisition info
        "format": str                 # 'nifti' or 'dicom'
    }
    """

    def __init__(self, path: str):
        self.path = path
        self.data: Optional[Dict[str, Any]] = None

    # PUBLIC API
    def load(self) -> Dict[str, Any]:
        """ Detect format and load file/folder """
        if not os.path.exists(self.path):
            # Note: should display error message in GUI instead of raising exception (to be implemented)
            raise FileNotFoundError(f"Path does not exist: {self.path}")
        
        if os.path.isdir(self.path): # assume a folder of dicom files
            self.data = self._load_dicom_series(self.path)
        else: # assume a single file (nifti or dicom)
            ext = os.path.splitext(self.path)[1].lower()
            if ext in ['.nii', '.nii.gz', '.gz']:
                try:
                    self.data = self._load_nifti_file(self.path)
                except Exception as e:
                    # Try DICOM as fallback for .gz (some DICOMs are .dcm.gz)
                    try:
                        self.data = self._load_dicom_file(self.path)
                    except:
                        raise ValueError(f"Unsupported or invalid file: {self.path} ({e})")        
            elif ext in ['.dcm']:
                self.data = self._load_dicom_file(self.path)
            else:
                # note: should also display GUI error message
                raise ValueError(f"Unsupported file format: {ext}")
        return self.data
    
    # NIfTI loader
    def _load_nifti_file(self, file_path: str) -> Dict[str, Any]:
        nii = nib.load(file_path)
        image = nii.get_fdata(dtype=np.float32)
        affine = nii.affine
        header = nii.header

        # Pad voxel_spacing with 1.0 for missing dimensions,
        # ensuring at least 3 values (e.g., for 2D: (dx, dy, 1.0)).
        # This maintains consistency with 3D output format.
        zooms = header.get_zooms()
        voxel_spacing = tuple(zooms[:3] + (1.0,) * (3 - len(zooms[:3])))
        metadata = {k: str(header[k]) for k in header.keys()}

        return {
            "image": image,
            "voxel_spacing": voxel_spacing,
            "orientation": affine,
            "metadata": metadata,
            "format": "nifti",
        }
    
    # DICOM loader
    def _load_dicom_file(self, file_path: str) -> Dict[str, Any]:
        """load a single dicom file"""
        ds = pydicom.dcmread(file_path)
        image = ds.pixel_array.astype(np.float32)

        image = self._apply_dicom_rescale(image, ds)

        voxel_spacing = self._get_dicom_spacing(ds)
        metadata = self._extract_metadata(ds)

        return {
            "image": image[np.newaxis, :, :],  # [Z, Y, X] for consistency
            "voxel_spacing": voxel_spacing,
            "orientation": self._compute_affine_single(ds),
            "metadata": metadata,
            "format": "dicom",
        }
    
    def _load_dicom_series(self, folder_path: str) -> Dict[str, Any]:
        folder_path = Path(folder_path)
        dicom_files = [f for f in folder_path.iterdir() if f.is_file()]
        if not dicom_files:
            raise ValueError(f"No files found in {folder_path}")

        dicoms = []
        for f in dicom_files:
            try:
                ds = pydicom.dcmread(f, stop_before_pixels=True)
                dicoms.append(ds)
            except Exception as e:
                print(f"⚠️ Skipping {f}: not a valid DICOM ({e})")

        if not dicoms:
            raise ValueError(f"No valid DICOM files in {folder_path}")
        
        first_ds = next((pydicom.dcmread(f) for f in dicom_files), None)
        if not first_ds:
            raise ValueError("No valid DICOM found")

        # Convert series to temporary NIfTI
        with tempfile.TemporaryDirectory() as temp_dir:
            output_nii = Path(temp_dir) / "series.nii.gz"
            dicom2nifti.convert_directory(folder_path, temp_dir, compression=True, reorient=True)

            # Find the generated NIfTI file
            nii_files = [f for f in Path(temp_dir).iterdir() if f.suffixes == ['.nii', '.gz']]
            if not nii_files:
                raise ValueError("No NIfTI files generated from DICOM series")
            
            # Pick the largest (likely most slices)
            output_nii = max(nii_files, key=lambda f: f.stat().st_size)

            # Load the generated NIfTI
            nii = nib.load(str(output_nii))
            image = nii.get_fdata(dtype=np.float32)
            affine = nii.affine
            header = nii.header
            voxel_spacing = tuple(header.get_zooms()[:3])

        return {
            "image": image,
            "voxel_spacing": voxel_spacing,
            "orientation": affine,
            "metadata": self._extract_metadata(first_ds),  # Use first DICOM for metadata
            "format": "dicom",  # Still mark as DICOM origin
        }

    # ---------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------
    def _get_dicom_spacing(self, ds: FileDataset) -> tuple:
        """Get voxel spacing (dx, dy, dz) from DICOM dataset."""
        try:
            pixel_spacing = [float(x) for x in ds.PixelSpacing]
            dz = float(getattr(ds, "SliceThickness", 1.0))
            return tuple((*pixel_spacing, dz))
        except Exception:
            return (1.0, 1.0, 1.0)
    
    def _apply_dicom_rescale(self, image: np.ndarray, ds: FileDataset) -> np.ndarray:
        """Apply rescale slope/intercept to DICOM pixel data"""
        slope = float(getattr(ds, 'RescaleSlope', 1.0))
        intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
        return image * slope + intercept

    def _extract_metadata(self, ds: FileDataset) -> Dict[str, Any]:
        """Extract relevant metadata safely."""
        fields = [
            "PatientName", "PatientID", "PatientAge", "PatientSex",
            "StudyDescription", "SeriesDescription", "Modality",
            "StudyDate", "Manufacturer", "SliceThickness", "Rows", "Columns",
        ]
        md = {}
        for field in fields:
            val = getattr(ds, field, None)
            if val is not None:
                md[field] = val # keep original type
        return md

    def _compute_affine_single(self, ds: FileDataset) -> np.ndarray:
        """Compute approximate affine for single DICOM slice."""
        try:
            orient = np.array(ds.ImageOrientationPatient, dtype=float).reshape(2, 3)
            row_dir, col_dir = orient
            normal_dir = np.cross(row_dir, col_dir)
            affine = np.eye(4)
            affine[:3, :3] = np.vstack((row_dir, col_dir, normal_dir)).T * [*ds.PixelSpacing, float(getattr(ds, "SliceThickness", 1.0))]
            affine[:3, 3] = np.array(ds.ImagePositionPatient, dtype=float)
            return affine
        except Exception:
            return np.eye(4)