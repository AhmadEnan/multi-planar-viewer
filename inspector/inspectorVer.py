# inspector_panel_vertical.py - Vertical Sidebar Layout (No Emojis)

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QLabel, QFileDialog, 
    QGroupBox, QMessageBox, QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from pathlib import Path
import sys

class ScrollLabel(QLabel):
    """A QLabel with automatic scrolling for long content"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

class InspectorPanelVertical(QWidget):
    """
    Vertical Medical File Inspector Panel - Optimized for Sidebar
    Files list on top, details below
    Automatically detects segmentation status
    """
    
    # Signal emitted when file is loaded: (filepath, has_segmentation)
    file_selected = Signal(str, bool)
    
    def __init__(self, main):
        super().__init__()
        self.current_directory = None
        self.available_files = []
        self.setup_ui()
        self.apply_styles()
        self.main = main
    
    def setup_ui(self):
        """Create the vertical user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # ===== TITLE =====
        title = QLabel("File Inspector")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setMaximumHeight(28)
        main_layout.addWidget(title)
        
        # ===== BROWSE BUTTON =====
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setMinimumHeight(32)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_directory)
        main_layout.addWidget(self.btn_browse)
        
        # Directory label
        self.dir_label = QLabel("No directory selected")
        self.dir_label.setWordWrap(True)
        self.dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dir_label.setMinimumHeight(35)
        self.dir_label.setMaximumHeight(50)
        self.dir_label.setStyleSheet("background-color: #1e1e1e; padding: 6px; border-radius: 4px; font-size: 9pt;")
        main_layout.addWidget(self.dir_label)
        
        # ===== FILE LIST SECTION =====
        file_list_label = QLabel("Medical Files")
        file_list_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        main_layout.addWidget(file_list_label)
        
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(200)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        main_layout.addWidget(self.file_list, stretch=2)
        
        # ===== FILE INFORMATION SECTION =====
        info_title = QLabel("Details")
        info_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        main_layout.addWidget(info_title)
        
        # Create scrollable info area
        info_scroll = QScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setMinimumHeight(150)
        info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.info_label = ScrollLabel("Select a file to see details")
        self.info_label.setStyleSheet("background-color: #1a1a1a; padding: 10px; border-radius: 4px;")
        info_scroll.setWidget(self.info_label)
        
        main_layout.addWidget(info_scroll, stretch=1)
        
        # ===== LOAD BUTTON =====
        self.btn_load = QPushButton("Load")
        self.btn_load.setMinimumHeight(40)
        self.btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load.setEnabled(False)
        self.btn_load.setObjectName("load_button")
        self.btn_load.clicked.connect(self.load_file)
        main_layout.addWidget(self.btn_load)
        
        self.setLayout(main_layout)
    
    def apply_styles(self):
        """Apply modern dark theme styling"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 9pt;
            }
            
            QPushButton {
                background-color: #3d5a80;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #4a6fa5;
            }
            
            QPushButton:pressed {
                background-color: #2c4460;
            }
            
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
            
            QPushButton#load_button {
                background-color: #2a9d8f;
                font-size: 10pt;
            }
            
            QPushButton#load_button:hover {
                background-color: #35c4b4;
            }
            
            QListWidget {
                background-color: #1e1e1e;
                border: 2px solid #3d5a80;
                border-radius: 6px;
                padding: 4px;
                color: #e0e0e0;
                font-size: 9pt;
            }
            
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            
            QListWidget::item:selected {
                background-color: #3d5a80;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #2d4560;
            }
            
            QLabel {
                color: #e0e0e0;
            }
            
            QScrollArea {
                border: 1px solid #3d5a80;
                border-radius: 6px;
                background-color: #1a1a1a;
            }
            
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3d5a80;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #4a6fa5;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
    
    # ========== CORE FUNCTIONALITY ==========
    
    def browse_directory(self):
        """Open directory picker and scan for NIfTI/DICOM files"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Directory with Medical Images",
            ""
        )
        
        if folder:
            self.current_directory = folder
            self.update_directory_display(folder)
            self.scan_directory()
    
    def scan_directory(self):
        """Scan current directory for NIfTI and DICOM files"""
        if not self.current_directory:
            return
        
        self.available_files = []
        self.file_list.clear()
        
        try:
            directory = Path(self.current_directory)
            
            # Find NIfTI files (.nii and .nii.gz)
            nifti_files = list(directory.glob("*.nii")) + list(directory.glob("*.nii.gz"))
            # Find DICOM files (.dcm)
            dicom_files = list(directory.glob("*.dcm"))
            
            # Combine and sort
            all_files = sorted(nifti_files + dicom_files)
            
            # Store all files
            for file in all_files:
                self.available_files.append(str(file))
                self.file_list.addItem(file.name)
            
            # Update UI with correct count
            total_count = len(self.available_files)
            
            if total_count == 0:
                self.file_list.addItem("No NIfTI or DICOM files found")
                self.btn_load.setEnabled(False)
                self.info_label.setText("No .nii, .nii.gz or .dcm files detected.")
            else:
                self.btn_load.setEnabled(True)
                self.info_label.setText("<b>Click on a file to see details</b>")
                
                # Auto-select first file
                if total_count > 0:
                    self.file_list.setCurrentRow(0)
                    self.show_file_info(self.available_files[0])
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Could not scan directory:\n{str(e)}"
            )
    
    def on_file_selected(self, row):
        """Handle file selection (single click)"""
        if row < 0 or row >= len(self.available_files):
            return
        
        filepath = self.available_files[row]
        self.show_file_info(filepath)
    
    def on_file_double_clicked(self, item):
        """Handle double-click on file"""
        self.load_file()
    
    def show_file_info(self, filepath):
        """Display file metadata with compact formatting for vertical layout"""
        try:
            path = Path(filepath)
            file_size_mb = path.stat().st_size / (1024 * 1024)
            
            # Auto-detect segmentation status
            has_segmentation = self.check_if_file_is_segmented(str(path))
            
            # Set status
            segmentation_status = "Already Segmented" if has_segmentation else "AI Segmentation Needed"
            segmentation_color = "#2a9d8f" if has_segmentation else "#f4a261"
            
            ext = path.suffix.lower()
            
            if ext == ".dcm":
                # DICOM file handling
                try:
                    import pydicom
                    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
                    patient = str(getattr(ds, "PatientName", "Unknown"))
                    modality = str(getattr(ds, "Modality", "N/A"))
                    study_date = str(getattr(ds, "StudyDate", "N/A"))
                    rows = getattr(ds, "Rows", "?")
                    cols = getattr(ds, "Columns", "?")
                    
                    info = f"""
                    <div style="line-height: 1.5; font-size: 9pt;">
                    <p style="margin: 2px 0;"><b>{path.name}</b></p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 3px solid {segmentation_color}; padding: 5px; margin: 8px 0; border-radius: 3px;">
                        <b style="color: {segmentation_color};">Status: {segmentation_status}</b>
                    </div>
                    
                    <p style="margin: 2px 0;"><b>Format:</b> DICOM<br>
                    <b>Patient:</b> {patient}<br>
                    <b>Modality:</b> {modality}<br>
                    <b>Date:</b> {study_date}<br>
                    <b>Dimensions:</b> {rows} × {cols}<br>
                    <b>Size:</b> {file_size_mb:.2f} MB</p>
                    </div>
                    """
                except ImportError:
                    info = f"""
                    <div style="line-height: 1.5; font-size: 9pt;">
                    <p style="margin: 2px 0;"><b>{path.name}</b></p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 3px solid {segmentation_color}; padding: 5px; margin: 8px 0; border-radius: 3px;">
                        <b style="color: {segmentation_color};">Status: {segmentation_status}</b>
                    </div>
                    
                    <p style="margin: 2px 0;"><b>Format:</b> DICOM<br>
                    <b>Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p style="margin: 5px 0; font-size: 8pt;"><i>Install pydicom for details</i></p>
                    </div>
                    """
                except Exception as e:
                    info = f"<p style='color: #e76f51;'>Error: {str(e)}</p>"
            
            elif ext in [".nii", ".gz"]:
                # NIfTI file handling
                try:
                    import nibabel as nib
                    img = nib.load(str(path))
                    shape = img.shape
                    spacing = img.header.get_zooms()
                    datatype = img.get_data_dtype()
                    
                    # Format dimensions
                    if len(shape) >= 3:
                        dim_info = f"{shape[0]}×{shape[1]}×{shape[2]}"
                    else:
                        dim_info = "×".join(str(s) for s in shape)
                    
                    # Format spacing
                    if len(spacing) >= 3:
                        spacing_info = f"{spacing[0]:.1f}×{spacing[1]:.1f}×{spacing[2]:.1f}mm"
                    else:
                        spacing_info = "×".join(f"{s:.1f}" for s in spacing) + "mm"
                    
                    info = f"""
                    <div style="line-height: 1.5; font-size: 9pt;">
                    <p style="margin: 2px 0;"><b>{path.name}</b></p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 3px solid {segmentation_color}; padding: 5px; margin: 8px 0; border-radius: 3px;">
                        <b style="color: {segmentation_color};">Status: {segmentation_status}</b>
                    </div>
                    
                    <p style="margin: 2px 0;"><b>Format:</b> NIfTI<br>
                    <b>Dimensions:</b> {dim_info}<br>
                    <b>Spacing:</b> {spacing_info}<br>
                    <b>Data Type:</b> {datatype}<br>
                    <b>Size:</b> {file_size_mb:.2f} MB</p>
                    </div>
                    """
                except ImportError:
                    info = f"""
                    <div style="line-height: 1.5; font-size: 9pt;">
                    <p style="margin: 2px 0;"><b>{path.name}</b></p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 3px solid {segmentation_color}; padding: 5px; margin: 8px 0; border-radius: 3px;">
                        <b style="color: {segmentation_color};">Status: {segmentation_status}</b>
                    </div>
                    
                    <p style="margin: 2px 0;"><b>Format:</b> NIfTI<br>
                    <b>Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p style="margin: 5px 0; font-size: 8pt;"><i>Install nibabel for details</i></p>
                    </div>
                    """
                except Exception as e:
                    info = f"<p style='color: #e76f51;'>Error: {str(e)}</p>"
            else:
                info = f"<p style='color: #f4a261;'>Unknown format</p>"
            
            self.info_label.setText(info)
        
        except Exception as e:
            self.info_label.setText(f"<p style='color: #e76f51;'>Error: {str(e)}</p>")
    
    def load_file(self):
        """Load the selected file and emit signal"""
        current_row = self.file_list.currentRow()
        
        if current_row < 0 or current_row >= len(self.available_files):
            QMessageBox.warning(
                self,
                "No File Selected",
                "Please select a file first."
            )
            return
        
        filepath = self.available_files[current_row]
        has_segmentation = self.check_if_file_is_segmented(filepath)
        
        # Emit signal
        self.file_selected.emit(filepath, has_segmentation)
        
        print(f"\n{'='*50}")
        print(f"FILE LOADED:")
        print(f"   Path: {filepath}")
        print(f"   Segmented: {'Yes' if has_segmentation else 'No'}")
        print(f"{'='*50}\n")

        self.main.load_path(filepath)
    
    # ========== HELPER METHODS ==========
    
    def check_if_file_is_segmented(self, filepath):
        """Check if file is segmented (optimized sampling)"""
        try:
            path = Path(filepath)
            ext = path.suffix.lower()
            
            if ext in [".nii", ".gz"]:
                try:
                    import nibabel as nib
                    import numpy as np
                    
                    img = nib.load(str(path))
                    shape = img.shape
                    total_voxels = np.prod(shape[:3])
                    
                    if total_voxels > 1_000_000:
                        data = img.dataobj
                        mid_z = shape[2] // 2
                        sample_indices = [0, mid_z, shape[2] - 1]
                        
                        samples = []
                        for z in sample_indices:
                            slice_data = data[:, :, z]
                            samples.append(slice_data[::10, ::10])
                        
                        sampled_data = np.concatenate([s.flatten() for s in samples])
                    else:
                        sampled_data = img.get_fdata().flatten()
                    
                    data_min = float(np.min(sampled_data))
                    data_max = float(np.max(sampled_data))
                    value_range = data_max - data_min
                    unique_values = np.unique(sampled_data)
                    num_unique = len(unique_values)
                    
                    all_integers = np.allclose(sampled_data, np.round(sampled_data))
                    has_nonzero = np.any(sampled_data > 0)
                    
                    is_segmentation = (
                        value_range <= 500 and
                        data_max <= 100 and
                        num_unique <= 100 and
                        all_integers and
                        has_nonzero
                    )
                    
                    return is_segmentation
                    
                except ImportError:
                    return False
                except Exception as e:
                    print(f"Error analyzing NIfTI: {e}")
                    return False
            
            elif ext == ".dcm":
                try:
                    import pydicom
                    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
                    
                    modality = str(getattr(ds, "Modality", ""))
                    sop_class = str(getattr(ds, "SOPClassUID", ""))
                    segmentation_sop = "1.2.840.10008.5.1.4.1.1.66.4"
                    
                    return (modality == "SEG" or sop_class == segmentation_sop)
                    
                except ImportError:
                    return False
                except Exception as e:
                    print(f"Error analyzing DICOM: {e}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"Error checking segmentation: {e}")
            return False
    
    def update_directory_display(self, directory):
        """Update directory label with shortened path"""
        display_path = directory
        if len(display_path) > 50:
            parts = display_path.split('/')
            if len(parts) > 3:
                display_path = f".../{parts[-2]}/{parts[-1]}"
            else:
                display_path = "..." + display_path[-47:]
        self.dir_label.setText(display_path)
    
    # ========== PUBLIC API ==========
    
    @property
    def selected_filepath(self):
        """Get currently selected file path"""
        row = self.file_list.currentRow()
        if 0 <= row < len(self.available_files):
            return self.available_files[row]
        return ""
    
    @property
    def has_segmentation(self):
        """Check if selected file has segmentation"""
        if self.selected_filepath:
            return self.check_if_file_is_segmented(self.selected_filepath)
        return False
    
    def get_all_files(self):
        """Get list of all discovered files"""
        return self.available_files.copy()


# ========== STANDALONE TEST ==========
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    inspector = InspectorPanelVertical()
    inspector.setWindowTitle("Medical File Inspector - Vertical")
    inspector.resize(350, 700)
    
    def on_file_loaded(filepath, has_seg):
        print(f"Signal received!")
        print(f"  Filepath: {filepath}")
        print(f"  Has segmentation: {has_seg}")
    
    inspector.file_selected.connect(on_file_loaded)
    
    inspector.show()
    sys.exit(app.exec())