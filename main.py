from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
import sys
from ui.viewer_manager import ViewerManager

class MainWindow(QMainWindow):       # This the main class for managing GUI, different from main class to manage the whole app
    def __init__(self):
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

                # Adding inspector content in the inspector frame
        self.dummy_label = QLabel("File Inspector Placeholder")
        self.dummy_label.setAlignment(Qt.AlignCenter)
        self.dummy_label.setStyleSheet("color: white; border: none; font-size: 15px;")
        self.inspector_frame_layout.addWidget(self.dummy_label)


            # Create viewer manger
        import nibabel as nib                               # for testing, replace it with serialization output
        nifti_file = nib.load(r"test_data/scan.nii.gz")
        self.viewer_manager = ViewerManager(nifti_file)       # pass the loaded nifti data ( e.g. nib.load(...) )
            
                                    # Comments For Anan

                        # To get roi extract data
                            # self.viewer_manager.extract_roi_data()
                            #               OR
                            # self.viewer_manager.get_roi_coordinates()

                        # Difference is explained in viewerManager_input_output.txt


        # Add frames to the central widget layout
        self.central_widget_layout.addWidget(self.inspector_frame, 1)
        self.central_widget_layout.addWidget(self.viewer_manager, 4)
        


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())