import os
import csv
import nibabel as nib
import numpy as np
import shutil
from totalsegmentator.python_api import totalsegmentator

class OrganSegmentator:
    def __init__(self):
        pass

    def segment(self, input_path, organs="liver", output_path="output"):
        """
        Segments organs and creates a CSV mapping slices to organs
        """
        patient_name = input_path.split(os.sep)[-1].split("/")[0]
        output_path = patient_name + "_" + output_path
        # Check if segmentation already exists
        if os.path.exists(output_path) and os.listdir(output_path):
            nifti_files = [f for f in os.listdir(output_path) if f.endswith('.nii.gz')]
            if nifti_files:
                print(f"Segmentation output already exists at {output_path}. Skipping segmentation.")
            else:
                # Directory exists but no segmentation files, run segmentation
                self._run_segmentation(input_path, organs, output_path)
        else:
            # Directory doesn't exist or is empty, run segmentation
            self._run_segmentation(input_path, organs, output_path)
        
        # Generate CSV mapping slices to organs, placeholder until we find a model that does this
        csv_path = os.path.join(output_path, "slice_organ_mapping.csv")
        self.create_slice_organ_csv(output_path, csv_path)
        
        return csv_path, output_path

    def _run_segmentation(self, input_path, organs, output_path):
        """
        Runs the actual segmentation process
        """
        totalsegmentator(
            input=input_path,
            output=output_path,
            roi_subset = organs,
            task='total',  
            fast=True,
            body_seg=True,
            force_split=False,
            nr_thr_saving=1,
            device= "cpu"
        )
        print(f"Segmentation completed. Results saved to {output_path}")

    def create_slice_organ_csv(self, output_path, csv_path):
        """
        Creates a CSV file mapping each slice to the organs present in it
        Memory-efficient version: loads one organ at a time
        """
        # Get all organ segmentation files
        organ_files = [f for f in os.listdir(output_path) if f.endswith('.nii.gz')]
        
        if not organ_files:
            print("No segmentation files found.")
            return
        
        # First pass: determine number of slices from first valid file
        num_slices = None
        for organ_file in organ_files:
            file_path = os.path.join(output_path, organ_file)
            try:
                nii = nib.load(file_path)
                data = nii.get_fdata()
                num_slices = data.shape[2]
                del nii, data  # Free memory
                break
            except Exception as e:
                print(f"Error loading {organ_file}: {e}")
                continue
        
        if num_slices is None:
            print("No valid organ data loaded.")
            return
        
        # Initialize slice-to-organs mapping
        slice_organs = {i: [] for i in range(num_slices)}
        
        # Second pass: process each organ file one at a time
        for organ_file in organ_files:
            organ_name = organ_file.replace('.nii.gz', '')
            file_path = os.path.join(output_path, organ_file)
            
            try:
                print(f"Processing {organ_name}...")
                nii = nib.load(file_path)
                data = nii.get_fdata()
                
                # Check each slice for this organ
                for slice_idx in range(num_slices):
                    if np.any(data[:, :, slice_idx] > 0):
                        slice_organs[slice_idx].append(organ_name)
                
                # Explicitly free memory
                del nii, data
                
            except Exception as e:
                print(f"Error processing {organ_file}: {e}")
                continue
        
        # Write CSV
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Slice_Index', 'Organs_Present'])
            
            for slice_idx in range(num_slices):
                organs_str = '; '.join(slice_organs[slice_idx]) if slice_organs[slice_idx] else 'None'
                writer.writerow([slice_idx, organs_str])
        
        print(f"CSV file created at: {csv_path}")
        print(f"Total slices processed: {num_slices}")

    def return_selected_organ(self, output_path, organ_name):
        """
        Returns the segmented organ file path
        """
        organ_file = os.path.join(output_path, f"{organ_name}.nii.gz")
        if os.path.exists(organ_file):
            print(f"Segmented organ file located at: {organ_file}")
            return organ_file
        else:
            print(f"Segmented organ file for {organ_name} not found.")
            return None
        
if __name__ == "__main__":
    organ_segmentator = OrganSegmentator()
    csv_path = organ_segmentator.segment(
        "test_data/scan.nii.gz",  # -------> Input path
        organs=["liver", 'brain', 'spleen', 'kidney_right', 'kidney_left',
                'heart', 'stomach'],  # List of organs to segment
        output_path="segmentations_out"
    )

    print(f"Segmentation complete! CSV saved at: {csv_path}")