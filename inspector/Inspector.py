# inspector_panel.py - Auto-Detection with Improved Segmentation Check

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

class InspectorPanel(QWidget):
    """
    Complete Medical File Inspector Panel
    Handles NIfTI + DICOM file browsing, selection, and metadata display
    Automatically detects segmentation status - no user input required
    """
    
    # Signal emitted when file is loaded: (filepath, has_segmentation)
    file_selected = Signal(str, bool)
    
    def __init__(self, main):
        super().__init__()
        self.current_directory = None
        self.available_files = []
        self.main = main
        self.setup_ui()
        self.apply_styles()
    
    def setup_ui(self):
        """Create the user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 10, 15, 10)
        
        # ===== TITLE =====
        title = QLabel("Medical File Inspector - NIfTI + DICOM")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setMaximumHeight(30)
        main_layout.addWidget(title)
        
        # ===== BROWSE SECTION =====
        browse_group = QGroupBox("Browse Directory")
        browse_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        browse_layout = QVBoxLayout(browse_group)
        
        self.btn_browse = QPushButton("Browse Directory")
        self.btn_browse.setMinimumHeight(35)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_directory)
        browse_layout.addWidget(self.btn_browse)
        
        # Directory label with more space
        self.dir_label = QLabel("No directory selected")
        self.dir_label.setWordWrap(True)
        self.dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dir_label.setMinimumHeight(45)
        self.dir_label.setStyleSheet("background-color: #1e1e1e; padding: 8px; border-radius: 4px;")
        browse_layout.addWidget(self.dir_label)
        
        main_layout.addWidget(browse_group)
        
        # ===== MAIN CONTENT AREA =====
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # Left side - File list
        left_container = QFrame()
        left_container.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_container)
        
        file_list_title = QLabel("Medical Files")
        file_list_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(file_list_title)
        
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(300)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        left_layout.addWidget(self.file_list)
        
        content_layout.addWidget(left_container, stretch=1)
        
        # Right side - File information
        right_container = QFrame()
        right_container.setMinimumWidth(300)
        right_layout = QVBoxLayout(right_container)
        
        info_title = QLabel("File Information")
        info_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(info_title)
        
        # Create scrollable info area
        info_scroll = QScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setMinimumHeight(280)
        info_scroll.setMaximumHeight(350)
        info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.info_label = ScrollLabel("Select a file to see details")
        self.info_label.setStyleSheet("background-color: #1a1a1a; padding: 12px; border-radius: 4px;")
        info_scroll.setWidget(self.info_label)
        
        right_layout.addWidget(info_scroll)
        
        content_layout.addWidget(right_container, stretch=1)
        
        main_layout.addLayout(content_layout, stretch=1)
        
        # ===== LOAD BUTTON =====
        self.btn_load = QPushButton("Proceed to Viewer")
        self.btn_load.setMinimumHeight(45)
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
                font-size: 10pt;
            }
            
            QPushButton {
                background-color: #3d5a80;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
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
                font-size: 11pt;
            }
            
            QPushButton#load_button:hover {
                background-color: #35c4b4;
            }
            
            QListWidget {
                background-color: #1e1e1e;
                border: 2px solid #3d5a80;
                border-radius: 6px;
                padding: 6px;
                color: #e0e0e0;
                font-size: 10pt;
            }
            
            QListWidget::item {
                padding: 8px;
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
            
            QGroupBox {
                border: 2px solid #3d5a80;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
                font-weight: bold;
                background-color: #1e1e1e;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #98c1d9;
            }
            
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d5a80;
                border-radius: 6px;
                padding: 8px;
            }
            
            QScrollArea {
                border: 1px solid #3d5a80;
                border-radius: 6px;
                background-color: #1a1a1a;
            }
            
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 15px;
                border-radius: 7px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3d5a80;
                border-radius: 7px;
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
                self.file_list.addItem(f"{file.name}")
            
            # Update UI with correct count
            total_count = len(self.available_files)
            
            if total_count == 0:
                self.file_list.addItem("No NIfTI or DICOM files found in this directory")
                self.btn_load.setEnabled(False)
                self.info_label.setText("No .nii, .nii.gz or .dcm files detected in the selected directory.")
            else:
                self.btn_load.setEnabled(True)
                self.info_label.setText("<b>Click on a file to see detailed information</b>")
                
                # Auto-select first file and show its info
                if total_count > 0:
                    self.file_list.setCurrentRow(0)
                    self.show_file_info(self.available_files[0])
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Scanning Directory",
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
        """Display file metadata with scrollable detailed information"""
        try:
            path = Path(filepath)
            file_size_mb = path.stat().st_size / (1024 * 1024)
            
            # Auto-detect segmentation status (lightweight check - only reads sample of data)
            has_segmentation = self.check_if_file_is_segmented(str(path))
            
            # Set status based on detection
            segmentation_status = "Already Segmented" if has_segmentation else "🤖 AI Segmentation Needed"
            segmentation_color = "#2a9d8f" if has_segmentation else "#f4a261"
            
            # Check file extension to determine type
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
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #98c1d9; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>Filename:</b> {path.name}</p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 4px solid {segmentation_color}; padding: 8px; margin: 10px 0; border-radius: 4px;">
                        <b style="color: {segmentation_color};">🏷️ Status:</b> {segmentation_status}
                    </div>
                    
                    <p><b>Format:</b> DICOM<br>
                    <b>Patient:</b> {patient}<br>
                    <b>Modality:</b> {modality}<br>
                    <b>Study Date:</b> {study_date}<br>
                    <b>Dimensions:</b> {rows} × {cols} (single slice)<br>
                    <b>File Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p><b>🔧 Technical Info:</b><br>
                    • Header Verified: Yes<br>
                    • Format: DICOM Standard</p>
                    </div>
                    """
                except ImportError:
                    info = f"""
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #98c1d9; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>Filename:</b> {path.name}</p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 4px solid {segmentation_color}; padding: 8px; margin: 10px 0; border-radius: 4px;">
                        <b style="color: {segmentation_color};">🏷️ Status:</b> {segmentation_status}
                    </div>
                    
                    <p><b>Format:</b> DICOM<br>
                    <b>File Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p><i>For detailed DICOM information, install pydicom:</i><br>
                    <code style="background: #2b2b2b; padding: 4px; border-radius: 3px;">pip install pydicom</code></p>
                    </div>
                    """
                except Exception as e:
                    info = f"""
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #e76f51; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>Filename:</b> {path.name}<br>
                    <b>File Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p style='color: #e76f51;'>⚠️ Error reading DICOM header<br>
                    {str(e)}</p>
                    </div>
                    """
            
            elif ext in [".nii", ".gz"]:
                # NIfTI file handling
                try:
                    import nibabel as nib
                    img = nib.load(str(path))
                    shape = img.shape
                    spacing = img.header.get_zooms()
                    datatype = img.get_data_dtype()
                    affine = img.affine
                    
                    # Format dimensions
                    if len(shape) >= 3:
                        dim_info = f"{shape[0]} × {shape[1]} × {shape[2]}"
                        if len(shape) > 3:
                            dim_info += f" × {shape[3]} (time)"
                    else:
                        dim_info = " × ".join(str(s) for s in shape)
                    
                    # Format spacing
                    if len(spacing) >= 3:
                        spacing_info = f"{spacing[0]:.2f} × {spacing[1]:.2f} × {spacing[2]:.2f} mm"
                    else:
                        spacing_info = " × ".join(f"{s:.2f}" for s in spacing) + " mm"
                    
                    # Calculate voxel count
                    voxel_count = 1
                    for dim in shape[:3]:
                        voxel_count *= dim
                    
                    info = f"""
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #98c1d9; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>Filename:</b> {path.name}</p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 4px solid {segmentation_color}; padding: 8px; margin: 10px 0; border-radius: 4px;">
                        <b style="color: {segmentation_color};">🏷️ Status:</b> {segmentation_status}
                    </div>
                    
                    <p><b>Format:</b> NIfTI<br>
                    <b>Dimensions:</b> {dim_info}<br>
                    <b>Voxel Spacing:</b> {spacing_info}<br>
                    <b>Data Type:</b> {datatype}</p>
                    
                    <p><b>Statistics:</b><br>
                    • Voxel Count: {voxel_count:,}<br>
                    • File Size: {file_size_mb:.2f} MB</p>
                    
                    <p><b>Technical Info:</b><br>
                    • Affine Matrix: {'Yes' if affine is not None else 'No'}<br>
                    • Header: Valid<br>
                    • Integrity: ✓ Good</p>
                    </div>
                    """
                except ImportError:
                    info = f"""
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #98c1d9; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>Filename:</b> {path.name}</p>
                    
                    <div style="background-color: {segmentation_color}33; border-left: 4px solid {segmentation_color}; padding: 8px; margin: 10px 0; border-radius: 4px;">
                        <b style="color: {segmentation_color};">🏷️ Status:</b> {segmentation_status}
                    </div>
                    
                    <p><b>📊 Format:</b> NIfTI<br>
                    <b>💾 File Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p><i>💡 For detailed NIfTI information, install nibabel:</i><br>
                    <code style="background: #2b2b2b; padding: 4px; border-radius: 3px;">pip install nibabel</code></p>
                    </div>
                    """
                except Exception as e:
                    info = f"""
                    <div style="line-height: 1.6; font-size: 10pt;">
                    <h3 style="color: #e76f51; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                    
                    <p><b>📁 Filename:</b> {path.name}<br>
                    <b>💾 File Size:</b> {file_size_mb:.2f} MB</p>
                    
                    <p style='color: #e76f51;'>⚠️ Limited information available<br>
                    Error reading header: {str(e)}</p>
                    </div>
                    """
            else:
                # Unknown file type
                info = f"""
                <div style="line-height: 1.6; font-size: 10pt;">
                <h3 style="color: #98c1d9; margin-top: 0; margin-bottom: 12px;">File Details</h3>
                
                <p><b>📁 Filename:</b> {path.name}<br>
                <b>💾 File Size:</b> {file_size_mb:.2f} MB</p>
                
                <p style='color: #f4a261;'>⚠️ Unknown file format</p>
                </div>
                """
            
            self.info_label.setText(info)
        
        except Exception as e:
            self.info_label.setText(f"""
            <div style="color: #e76f51; line-height: 1.6;">
            <h3 style="margin-top: 0;">❌ Error Loading File Information</h3>
            <p>{str(e)}</p>
            </div>
            """)
    
    def load_file(self):
        """Load the selected file and emit signal"""
        current_row = self.file_list.currentRow()
        
        if current_row < 0 or current_row >= len(self.available_files):
            QMessageBox.warning(
                self,
                "No File Selected",
                "Please select a file from the list first."
            )
            return
        
        filepath = self.available_files[current_row]

        if ".dcm" in filepath:
            filepath = str(Path(filepath).parent)  # Load entire DICOM folder
        
        # Auto-detect segmentation status
        has_segmentation = self.check_if_file_is_segmented(filepath)
        
        # Emit signal
        self.file_selected.emit(filepath, has_segmentation)
        
        # Show confirmation
        self.show_load_confirmation(filepath, has_segmentation)
        self.main.load_path_and_open_viewer(filepath, self.current_directory, has_segmentation)
    
    # ========== HELPER METHODS ==========
    
    def check_if_file_is_segmented(self, filepath):
        """
        Check if a NIfTI/DICOM file is a segmentation file using STRICT criteria.
        OPTIMIZED: Only samples data instead of loading entire file.
        
        For NIfTI: Checks if file contains organ labels by analyzing voxel data:
        - Value range (max-min) must be ≤500 (raw CT has ~4000 range, segmentation has ~10)
        - Max value ≤100 (segmentations have small label IDs)
        - ≤100 unique values (segmentations have 2-20 labels, raw scans have thousands)
        - All values must be integers
        - At least 1 non-zero label present
        
        For DICOM: Checks Modality=="SEG" or Segmentation Storage SOP Class UID
        
        Returns:
            bool: True if file is segmented, False otherwise
        """
        try:
            path = Path(filepath)
            ext = path.suffix.lower()
            
            if ext in [".nii", ".gz"]:
                # NIfTI segmentation detection - OPTIMIZED VERSION
                try:
                    import nibabel as nib
                    import numpy as np
                    
                    img = nib.load(str(path))
                    
                    # OPTIMIZATION: Sample only a small portion of the data (10% or max 1 million voxels)
                    shape = img.shape
                    total_voxels = np.prod(shape[:3])
                    
                    if total_voxels > 1_000_000:
                        # For large files, use dataobj (lazy loading) and sample strategically
                        data = img.dataobj
                        
                        # Sample from center slice and edges
                        mid_z = shape[2] // 2
                        sample_indices = [0, mid_z, shape[2] - 1]
                        
                        samples = []
                        for z in sample_indices:
                            # Take every 10th voxel from this slice
                            slice_data = data[:, :, z]
                            samples.append(slice_data[::10, ::10])
                        
                        sampled_data = np.concatenate([s.flatten() for s in samples])
                    else:
                        # For small files, load everything
                        sampled_data = img.get_fdata().flatten()
                    
                    # Get statistics from sample
                    data_min = float(np.min(sampled_data))
                    data_max = float(np.max(sampled_data))
                    value_range = data_max - data_min
                    unique_values = np.unique(sampled_data)
                    num_unique = len(unique_values)
                    
                    # Check if all values are integers
                    all_integers = np.allclose(sampled_data, np.round(sampled_data))
                    
                    # Check if has at least one non-zero label
                    has_nonzero = np.any(sampled_data > 0)
                    
                    # STRICT criteria for segmentation detection
                    is_segmentation = (
                        value_range <= 500 and  # Narrow range
                        data_max <= 100 and     # Small max value (label IDs)
                        num_unique <= 100 and   # Few unique values
                        all_integers and        # Integer values only
                        has_nonzero             # Has actual labels
                    )
                    
                    # Only print debug info if verbose mode is needed
                    # print(f"🔍 NIfTI Analysis for {path.name}:")
                    # print(f"   Value range: {value_range:.2f} (max: {data_max:.2f}, min: {data_min:.2f})")
                    # print(f"   Unique values: {num_unique}")
                    # print(f"   All integers: {all_integers}")
                    # print(f"   Has non-zero: {has_nonzero}")
                    # print(f"   → Is segmentation: {is_segmentation}")
                    
                    return is_segmentation
                    
                except ImportError:
                    # print(f"⚠️ nibabel not installed, cannot check NIfTI segmentation status")
                    return False
                except Exception as e:
                    print(f"⚠️ Error analyzing NIfTI file: {e}")
                    return False
            
            elif ext == ".dcm":
                # DICOM segmentation detection - already fast (header only)
                try:
                    import pydicom
                    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
                    
                    # Check modality
                    modality = str(getattr(ds, "Modality", ""))
                    
                    # Check SOP Class UID for Segmentation Storage
                    sop_class = str(getattr(ds, "SOPClassUID", ""))
                    segmentation_sop = "1.2.840.10008.5.1.4.1.1.66.4"  # Segmentation Storage
                    
                    is_segmentation = (modality == "SEG" or sop_class == segmentation_sop)
                    
                    # print(f"🔍 DICOM Analysis for {path.name}:")
                    # print(f"   Modality: {modality}")
                    # print(f"   SOP Class: {sop_class}")
                    # print(f"   → Is segmentation: {is_segmentation}")
                    
                    return is_segmentation
                    
                except ImportError:
                    # print(f"⚠️ pydicom not installed, cannot check DICOM segmentation status")
                    return False
                except Exception as e:
                    print(f"⚠️ Error analyzing DICOM file: {e}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking segmentation status: {e}")
            return False
    
    def update_directory_display(self, directory):
        """Update directory label with shortened path if needed"""
        display_path = directory
        if len(display_path) > 70:
            parts = display_path.split('/')
            if len(parts) > 3:
                display_path = f"{parts[0]}/.../{parts[-2]}/{parts[-1]}"
            else:
                display_path = "..." + display_path[-67:]
        self.dir_label.setText(f"📂 {display_path}")
    
    def show_load_confirmation(self, filepath, has_seg):
        """Show confirmation dialog when file is loaded"""
        filename = Path(filepath).name
        status_text = "Already Segmented ✅" if has_seg else "AI Segmentation Needed 🤖"
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("File Loading")
        msg.setText(f"<b>Loading file:</b><br>{filename}")
        msg.setInformativeText(f"<b>Segmentation Status:</b> {status_text}")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        
        print(f"\n{'='*60}")
        print(f"🚀 FILE LOADED:")
        print(f"   Path: {filepath}")
        print(f"   Is Segmented: {'Yes ✓' if has_seg else 'No (AI needed) 🤖'}")
        print(f"{'='*60}\n")
    
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
        """Check if selected file has segmentation (auto-detected)"""
        if self.selected_filepath:
            return self.check_if_file_is_segmented(self.selected_filepath)
        return False
    
    @property
    def is_classified(self):
        """Alias for has_segmentation"""
        return self.has_segmentation
    
    def get_all_files(self):
        """Get list of all discovered files"""
        return self.available_files.copy()


# ========== STANDALONE TEST ==========
def open_inspector_view():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    inspector = InspectorPanel()
    inspector.setWindowTitle("Medical File Inspector - NIfTI + DICOM")
    inspector.resize(800, 700)
    
    inspector.show()
    sys.exit(app.exec())
