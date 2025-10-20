# serialization/saver.py
# This file is part of the Multi-Planar Viewer project.
# It is responsible for loading serialized data.

import os
import numpy as np
import nibabel as nib
import SimpleITK as sitk
from typing import Dict, Any, Tuple


def crop_roi(data: Dict[str, Any], bounds: Tuple[int, int, int, int, int, int]) -> Dict[str, Any]:
    """
    Crop ROI (Region of Interest) from a loaded 3D volume.

    Parameters
    ----------
    data : dict
        The loaded dataset dictionary from DataLoader.
    bounds : tuple
        (z_min, z_max, y_min, y_max, x_min, x_max) voxel indices.

    Returns
    -------
    dict
        Cropped volume dictionary with adjusted affine and metadata.
    """
    img = data["image"]
    cropped = img[bounds[0]:bounds[1], bounds[2]:bounds[3], bounds[4]:bounds[5]]

    affine = data["orientation"].copy()
    voxel_spacing = np.array(data["voxel_spacing"])

    # Update affine translation to match new cropped origin
    translation = np.array([bounds[4], bounds[2], bounds[0], 0]) * np.append(voxel_spacing, 1)
    affine[:3, 3] += translation[:3]

    return {
        "image": cropped,
        "voxel_spacing": tuple(voxel_spacing),
        "orientation": affine,
        "metadata": data.get("metadata", {}),
        "format": data.get("format", "unknown"),
    }


def export_nifti(cropped_data: Dict[str, Any], header, output_path: str):
    """Export a cropped ROI to a NIfTI (.nii or .nii.gz) file."""
    img = cropped_data["image"]
    affine = cropped_data["orientation"]
    nii = nib.Nifti1Image(img, affine, header=header)
    nib.save(nii, output_path)


def export_dicom(cropped_data: Dict[str, Any], output_folder: str):
    """Export a cropped ROI to a DICOM series folder."""
    os.makedirs(output_folder, exist_ok=True)

    img = sitk.GetImageFromArray(cropped_data["image"])
    img.SetSpacing(cropped_data["voxel_spacing"])
    img.SetOrigin(cropped_data["orientation"][:3, 3])

    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    for i in range(img.GetDepth()):
        slice_i = img[:, :, i]
        slice_path = os.path.join(output_folder, f"slice_{i:03d}.dcm")
        writer.SetFileName(slice_path)
        writer.Execute(slice_i)


def export_roi(data: Dict[str, Any], bounds: Tuple[int, int, int, int, int, int], output_path: str, fmt: str, header=None):
    """High-level helper for exporting ROI to NIfTI or DICOM."""
    cropped = crop_roi(data, bounds)

    if fmt.lower() in ["nii", "nifti", ".nii", ".nii.gz"]:
        export_nifti(cropped, header, output_path)
    elif fmt.lower() == "dicom":
        export_dicom(cropped, output_path)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

# Example usage 
# -----------------------------------------------------------
# bounds = (20, 80, 50, 150, 40, 140)  # example ROI indices
# export_roi(data, bounds, 'roi_output.nii.gz', 'nifti')