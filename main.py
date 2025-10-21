from PySide6.QtWidgets import *
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer
import sys
import torch
import nibabel as nib
from ui.viewer_manager import ViewerManager
from serialization.loader import DataLoader
from serialization import saver 
from ai.orientation_classification import MRIOrientationClassifier
from ai.segmentator import OrganSegmentator
from inspector.inspectorVer import InspectorPanelVertical
from inspector.Inspector import InspectorPanel, open_inspector_view
from collections import Counter
import csv


# The main class which manage the inputs and output of all other classes
class Main:
    def __init__(self):
        super().__init__()


        # Opening the Inespector at the start of the app
    
        self.current_file_path = None
        self.main_inspector = InspectorPanel(self)
        self.main_inspector.show()


        # Loading file
    def load_data(self):
        loader = DataLoader(self.current_file_path)

        
        self.data = loader.load()
        img, affine = self.data["image"], self.data[ "orientation"]
        self.header = self.data.get("header", None)
        self.nifti_data = nib.Nifti1Image(img, affine)
        self.orientation = self.run_classifier_ai()
        if self.has_segmentation:
            self.csv_path, self.seg_out_path = 'segmentations_out/slice_organ_mapping.csv','segmentations_out'
        else:
            self.csv_path, self.seg_out_path = self.run_segmentator_ai()


    def load_path(self, path):
        self.current_file_path = path
        self.load_data()
        self.window.update_viewer()


    def load_path_and_open_viewer(self, path, folder, has_segmentation=False):
        self.current_file_path = path
        self.current_directory = folder
        self.has_segmentation = has_segmentation
        self.main_inspector.close()
        self.load_data()
        self.open_viewer()

    def run_classifier_ai(self):
        "Initialize classifier"
        classifier = MRIOrientationClassifier(
            checkpoint_path="ai/model_checkpoint/mri_orientation_finetuned.pth",
            mri_foundation_path=None,
            device="cuda" if torch.cuda.is_available() else 'cpu'  # or "cpu"
        )

        # # Example 1: Predict from NIfTI file
        img = self.nifti_data
        axial_count = 0
        sagittal_count = 0
        coronal_count = 0
        print(f"\nPredicting for NIfTI slice {img.shape[2]//2}")
        result = classifier.predict_from_nifti(self.nifti_data, slice_index=img.shape[2]//2)
        if result['orientation'] == 'Axial':
            axial_count += 1
        if result['orientation'] == 'Coronal':
            coronal_count += 1
        if result['orientation'] == 'Sagittal':
            sagittal_count += 1
        print(f"\nPrediction Results:")
        print(f"  Orientation: {result['orientation']}")
        print(f"  Confidence: {result['confidence']:.4f}")
        print(f"  All probabilities: {result['all_probabilities']}")

        counts = {
        'Axial': axial_count,
        'Coronal': coronal_count,
        'Sagittal': sagittal_count
        }

        predicted_orientation = max(counts, key=counts.get)
        print(f'Final Prediction : {predicted_orientation}')
        return predicted_orientation

    def run_segmentator_ai(self):
        "Initialize segmentator"
        organ_segmentator = OrganSegmentator()
        csv_path, output_path = organ_segmentator.segment(
            self.current_file_path,  # -------> Input path
            organs=["liver", 'brain', 'spleen', 'kidney_right', 'kidney_left',
                    'heart', 'stomach'],  # List of organs to segment
            output_path="segmentations_out"
        )
        print(f"Segmentation CSV saved at: {csv_path}")
        return csv_path, output_path

    def open_viewer(self):
        "Open the Main Window GUI"
        self.window = MainWindow(self, self.nifti_data)
        self.window.show()
        QTimer.singleShot(50, self.window.showMaximized)


    def export_roi(self):
        if self.window.export_roi_action:
            roi_voxels_coordinates = self.window.viewer_manager.get_roi_voxel_coordinates()
            saver.export_roi(self.data, roi_voxels_coordinates, "exported_roi/exported_roi.nii.gz", fmt="nifti", header=self.header)
            print("ROI exported to: exported_roi/exported_roi.nii.gz")
        else:
            print("No ROI selected for export.")
        
        


# This the main class for managing GUI
class MainWindow(QMainWindow):
    def __init__(self, main, nifti_data):
        super().__init__()
        self.main = main
        self.setWindowTitle("MPR Viewer")

        # Create a menubar
        self.menu = self.menuBar()
        self.menu.setStyleSheet("background-color: #2d2d2d; color: white;")
        self.file_menu = self.menu.addMenu("&File")

        self.open_action = QAction("&Open", self)
        self.open_action.setShortcut("Ctrl+O")

        self.export_roi_action = QAction("&Export ROI", self)
        self.export_roi_action.setShortcut("Ctrl+E")

        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.export_roi_action)

        self.export_roi_action.triggered.connect(self.main.export_roi)

        # create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget_layout = QHBoxLayout(self.central_widget)
        self.central_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.central_widget_layout.setSpacing(0)

            ## # create a file inspector     ---> this block will be replaced with inspector class       
        self.inspector_frame = QFrame(self.central_widget)
        self.inspector_frame.setFrameShape(QFrame.StyledPanel)
        self.inspector_frame.setStyleSheet("""
            QFrame {
                border-radius: 0px;
                background-color: #2a2a2a;
                border: 0.3px solid #444;
                }""")
        

        self.inspector_frame_layout = QVBoxLayout(self.inspector_frame)
        self.inspector_frame_layout.setStretch(0,1)

        # Adding Viewer Manager
        organ = self.most_common_organ(self.main.csv_path)
        print(f'Main organ: {organ}')
        self.viewer_manager = ViewerManager(nifti_data, segmentation_mask=f'{self.main.seg_out_path}/{organ}.nii.gz', main_organ=organ, orientation=self.main.orientation)
        # self.viewer_manager = ViewerManager(nifti_data, segmentation_mask=f'{self.main.seg_out_path}/{organ}.nii.gz', main_organ=organ, orientation='AXIAL')
        self.open_side_inspector()

        self.open_action.triggered.connect(self.inspector.browse_directory)

        # Add frames to the central widget layout
        self.central_widget_layout.addWidget(self.inspector_frame, 1)
        self.central_widget_layout.addWidget(self.viewer_manager, 4)

    def update_viewer(self):
        if hasattr(self, 'viewer_manager'):
            self.central_widget_layout.removeWidget(self.viewer_manager)
            self.viewer_manager.deleteLater()
            organ = self.most_common_organ(self.main.csv_path)
            print(f'Main organ: {organ}')
            self.viewer_manager = ViewerManager(self.main.nifti_data, segmentation_mask=f'{self.main.seg_out_path}/{organ}.nii.gz', main_organ=organ, orientation=self.main.orientation)
            # self.viewer_manager = ViewerManager(self.main.nifti_data, segmentation_mask=f'{self.main.seg_out_path}/{organ}.nii.gz', main_organ=organ, orientation='axial')

            self.central_widget_layout.addWidget(self.viewer_manager, 4)
            
    def most_common_organ(self,csv_path):
        organ_counts = Counter()

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                organs = [org.strip().lower() for org in row["Organs_Present"].split(';')]
                for organ in organs:
                    if organ and organ != "none":
                        organ_counts[organ] += 1

        most_common = organ_counts.most_common(1)
        if most_common:
            organ, count = most_common[0]
            return organ
        else:
            return None
        
    def open_side_inspector(self):
        "Adding inspector content in the inspector frame"
        self.inspector = InspectorPanelVertical(self.main)
        self.inspector.current_directory = self.main.current_directory
        self.inspector.update_directory_display(self.main.current_directory)
        self.inspector.scan_directory()
        self.inspector_frame_layout.addWidget(self.inspector)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main = Main()
    sys.exit(app.exec())