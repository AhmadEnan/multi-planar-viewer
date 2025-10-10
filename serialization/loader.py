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
from collections import defaultdict


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
                self.data = self._load_nifti_file(self.path)
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

        voxel_spacing = tuple(header.get_zooms()[:3])
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
        voxel_spacing = self._get_dicom_spacing(ds)
        metadata = self._extract_metadata(ds)

        return {
            "image": image[np.newaxis, :, :],  # [Z, Y, X] for consistency
            "voxel_spacing": voxel_spacing,
            "orientation": self._compute_affine_single(ds),
            "metadata": metadata,
            "format": "dicom",
        }
    
    # def _load_dicom_series(self, folder_path: str) -> Dict[str, Any]:
    #     """Load all DICOM files in a folder as a 3D volume"""

    #     files = []
    #     for f in os.listdir(folder_path):
    #         full_path = os.path.join(folder_path, f)
    #         try:
    #             ds = pydicom.dcmread(full_path, stop_before_pixels=True)
    #             if hasattr(ds, "InstanceNumber"):
    #                 files.append(full_path)
    #         except Exception:
    #             continue

    #     if not files:
    #         raise ValueError("No valid DICOM files found in folder.")

    #     # Sort by InstanceNumber or SliceLocation
    #     dicoms: List[FileDataset] = []
    #     for f in files:
    #         try:
    #             ds = pydicom.dcmread(f)
    #             dicoms.append(ds)
    #         except Exception as e:
    #             print(f"Warning: Skipping {f}: {e}")

    #     dicoms.sort(key=lambda d: getattr(d, "InstanceNumber", 0))
    #     for d in dicoms:
    #         print(d.SOPInstanceUID, d.pixel_array.shape)

    #     # Stack into 3D volume
    #     image_stack = np.stack([d.pixel_array for d in dicoms]).astype(np.float32)

    #     voxel_spacing = self._get_dicom_spacing(dicoms[0])
    #     orientation = self._compute_affine_series(dicoms)
    #     metadata = self._extract_metadata(dicoms[0])

    #     return {
    #         "image": image_stack,            # [Z, Y, X]
    #         "voxel_spacing": voxel_spacing,  # (dx, dy, dz)
    #         "orientation": orientation,      # 4x4 matrix
    #         "metadata": metadata,
    #         "format": "dicom",
    #     }

    def _load_dicom_series(self, folder_path):
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

        # Group by SeriesInstanceUID
        series_dict = defaultdict(list)
        for d in dicoms:
            uid = getattr(d, "SeriesInstanceUID", None)
            if uid:
                series_dict[uid].append(pydicom.dcmread(d.filename))

        if not series_dict:
            raise ValueError("No DICOM series found in this folder.")

        # Pick the largest one (most slices)
        main_series = max(series_dict.values(), key=len)

        # Sort by slice position
        try:
            main_series.sort(key=lambda d: float(d.ImagePositionPatient[2]))
        except Exception:
            pass

        # Verify consistent shape
        shapes = [d.pixel_array.shape for d in main_series]
        if len(set(shapes)) > 1:
            raise ValueError(f"Inconsistent slice shapes: {set(shapes)}")

        # Stack into 3D volume
        image_stack = np.stack([d.pixel_array for d in main_series]).astype(np.float32)

        slope = float(main_series[0].get("RescaleSlope", 1.0))
        intercept = float(main_series[0].get("RescaleIntercept", 0.0))
        image_stack = image_stack * slope + intercept

        pixel_spacing = list(getattr(main_series[0], "PixelSpacing", [1, 1]))
        slice_thickness = float(getattr(main_series[0], "SliceThickness", 1.0))
        metadata = self._extract_metadata(main_series[0])

        return {
            "image": image_stack,
            "metadata": metadata,
            "PatientName": str(getattr(main_series[0], "PatientName", "Unknown")),
            "PatientID": str(getattr(main_series[0], "PatientID", "Unknown")),
            "Modality": str(getattr(main_series[0], "Modality", "Unknown")),
            "SeriesDescription": str(getattr(main_series[0], "SeriesDescription", "Unknown")),
            "VoxelSpacing": pixel_spacing + [slice_thickness],
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
                md[field] = str(val)
        return md

    def _compute_affine_series(self, dicoms: List[FileDataset]) -> np.ndarray:
        """Compute approximate affine transform for DICOM series."""
        try:
            ds0, ds1 = dicoms[0], dicoms[1]
            pos0 = np.array(ds0.ImagePositionPatient, dtype=float)
            pos1 = np.array(ds1.ImagePositionPatient, dtype=float)
            orient = np.array(ds0.ImageOrientationPatient, dtype=float).reshape(2, 3)
            row_dir, col_dir = orient
            normal_dir = np.cross(row_dir, col_dir)
            dz = np.linalg.norm(pos1 - pos0)
            affine = np.eye(4)
            affine[:3, :3] = np.vstack((row_dir, col_dir, normal_dir)).T * [*ds0.PixelSpacing, dz]
            affine[:3, 3] = pos0
            return affine
        except Exception:
            return np.eye(4)

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