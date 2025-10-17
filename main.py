from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
import sys
import torch
from ui.viewer_manager import ViewerManager
from serialization.loader import DataLoader
from ai.orientation_classification import MRIOrientationClassifier
from inspector import Inspector, inspectorVer



# The main class which manage the inputs and output of all other classes
class Main:
    def __init__(self):
        super().__init__()


        # Opening the Inespector at the start of the app

        self.current_file_path = r"test_data\scan.nii.gz"
        # Loading file
        import nibabel as nib

        loader = DataLoader(self.current_file_path)

        data = loader.load()
        img, affine = data["image"], data[ "orientation"]
        self.nifti_data = nib.Nifti1Image(img, affine)

        self.open_viewer()
        


    def run_classifier_ai(self):
        "Initialize classifier"
        classifier = MRIOrientationClassifier(
            checkpoint_path="ai/mri_orientation_finetuned.pth",
            mri_foundation_path=None,
            device="cuda" if torch.cuda.is_available() else 'cpu'  # or "cpu"
        )

        # # Example 1: Predict from NIfTI file
        img = self.nifti_data
        axial_count = 0
        sagittal_count = 0
        coronal_count = 0
        for i in range(0 , img.shape[2], 40):
            print(f"\nPredicting for NIfTI slice {i}")
            result = classifier.predict_from_nifti(nifti_file=self.nifti_data, slice_index=i)
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
            if i == 5*40 :
                break

        counts = {
        'Axial': axial_count,
        'Coronal': coronal_count,
        'Sagittal': sagittal_count
        }

        predicted_orientation = max(counts, key=counts.get)
        print(f'Final Prediction : {predicted_orientation}')

    

    def open_inspector(self):
        "Open the inspector side window"
        pass
    

    def open_viewer(self):
        "Open the Main Window GUI"
        window = MainWindow(self.nifti_data)
        window.showMaximized()

        sys.exit(app.exec())


# This the main class for managing GUI
class MainWindow(QMainWindow):
    def __init__(self, nifti_data):
        super().__init__()

        self.setWindowTitle("MPR Viewer")

        # Create a menubar
        self.menu = self.menuBar()
        self.menu.setStyleSheet("background-color: #2d2d2d; color: white;")
        self.file_menu = self.menu.addMenu("&File")

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
        self.viewer_manager = ViewerManager(nifti_data)
        self.open_side_inspector()


        # Add frames to the central widget layout
        self.central_widget_layout.addWidget(self.inspector_frame, 1)
        self.central_widget_layout.addWidget(self.viewer_manager, 4)
        
    def open_side_inspector(self):
        "Adding inspector content in the inspector frame"
        self.inspector = inspectorVer.InspectorPanelVertical()
        self.inspector_frame_layout.addWidget(self.inspector)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main = Main()