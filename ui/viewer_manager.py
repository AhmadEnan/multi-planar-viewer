from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction, QPen, QPainter, QColor, QMouseEvent
import nibabel as nib
import numpy as np


class ViewerManager(QFrame):
    def __init__(self, loaded_nifti=None):
        super().__init__()

        self.nifti_file = loaded_nifti

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                border-radius: 0px;
                background-color: #1e1e1e;
                border: 0px solid #333;
            }""")
        
        self.viewer_frame_layout = QGridLayout(self)
        self.viewer_frame_layout.setContentsMargins(0,0,0,0)
        self.viewer_frame_layout.setSpacing(0)
        
        # Adding toolbar
        self.toolbar = QToolBar("Viewer Toolbar", self)
        self.toolbar.setStyleSheet("background-color: #2d2d2d; color: white;")

        roi_icon = QIcon(r".\icons\roi_icon.png")
        self.roi_action = QAction(roi_icon, "Toggle ROI", self)
        self.roi_action.setToolTip("ROI display")
        self.roi_action.setCheckable(True)
        self.roi_action.triggered.connect(self._toggle_roi)
        self.toolbar.addAction(self.roi_action)

        axis_icon = QIcon(r".\icons\axis_icon.png")
        self.axis_action = QAction(axis_icon, "Show Axes", self)
        self.axis_action.setToolTip("Axes display")
        self.axis_action.triggered.connect(self._toggle_axes)
        self.toolbar.addAction(self.axis_action)
        self.axis_action.setCheckable(True)

        self.toolbar.addSeparator()
        
        # Adding fourth view tools
        oblique_icon = QIcon(r"icons/oblique_icon.png")
        self.oblique_action = QAction(oblique_icon, "Show oblique view", self)
        self.axis_action.setToolTip("Display oblique in the 4th view")
        self.oblique_action.triggered.connect(self._show_oblique)
        self.toolbar.addAction(self.oblique_action)
        self.oblique_action.setCheckable(True)

        outline_icon = QIcon(r"icons/outline_icon.png")
        self.outline_action = QAction(outline_icon, "Show outline view", self)
        self.axis_action.setToolTip("Display the organ outline in the 4th view")
        self.outline_action.triggered.connect(self._show_outline)
        self.toolbar.addAction(self.outline_action)
        self.outline_action.setCheckable(True)

            # Drop down to choose the required view to take data from it
        self.base_view_to4th = None

        self.tool_button = QToolButton(self)
        self.tool_button.setToolTip("Choose a Base view to make the fourth view on it")
        self.tool_button.setText("Base View")
        self.tool_button.setStyleSheet("color: grey;")
        self.tool_button.setEnabled(False)
        # tool_button.setIcon(QIcon("path/to/your/icon.png")) # Optional: Set an icon
        self.toolbar.addWidget(self.tool_button)

        self.dropdown_menu = QMenu(self)
        action1 = QAction("axial", self)
        action2 = QAction("sagittal", self)
        action3 = QAction("coronal", self)
        self.dropdown_menu.addAction(action1)
        self.dropdown_menu.addAction(action2)
        self.dropdown_menu.addAction(action3)


        action1.triggered.connect(lambda: self._set_base_view("axial"))
        action2.triggered.connect(lambda: self._set_base_view("sagittal"))
        action3.triggered.connect(lambda: self._set_base_view("coronal"))

        self.tool_button.setMenu(self.dropdown_menu)
        self.tool_button.setPopupMode(QToolButton.MenuButtonPopup) # Or QToolButton.DelayedPopup, QToolButton.MenuButtonPopup
        self.dropdown_menu.popup(self.tool_button.mapToGlobal(self.tool_button.rect().bottomLeft()))

        self.toolbar.addSeparator()

        self.viewer_frame_layout.addWidget(self.toolbar, 0, 0, 1, 2)

        # Preprocessing NIFTI data
        img_ras = nib.as_closest_canonical(self.nifti_file)
        self.affine = img_ras.affine
        self.inv_affine = np.linalg.inv(self.affine)
        
        self.data = img_ras.get_fdata()
        shape = np.array(self.data.shape)
        
        # Initialize cursor at center (in voxel coordinates)
        self.cursor_voxel = (shape - 1) / 2  # [i, j, k]
        self.cursor_world = self._voxel_to_world(self.cursor_voxel)

        # Control flags
        self.crosshair_enabled = False
        self.roi_enabled = False

        # ROI bounds (in voxel coordinates) - 1/3 of volume centered
        roi_size = shape / 3
        center = self.cursor_voxel.copy()
        
        # Initialize ROI around center point with integer coordinates
        self.roi_start = np.array([
            max(0, int(center[0] - roi_size[0]/2)),
            max(0, int(center[1] - roi_size[1]/2)),
            max(0, int(center[2] - roi_size[2]/2))
        ])
        
        self.roi_end = np.array([
            min(shape[0]-1, int(center[0] + roi_size[0]/2)),
            min(shape[1]-1, int(center[1] + roi_size[1]/2)),
            min(shape[2]-1, int(center[2] + roi_size[2]/2))
        ])
        
        # Ensure ROI has some minimum size
        min_size = 10  # minimum size in voxels
        for i in range(3):
            if self.roi_end[i] - self.roi_start[i] < min_size:
                center_i = (self.roi_start[i] + self.roi_end[i]) // 2
                self.roi_start[i] = max(0, center_i - min_size//2)
                self.roi_end[i] = min(shape[i]-1, center_i + min_size//2)

        # Create viewports
        self.viewports = {}
        
        self.viewports['axial'] = ViewPort(self, orientation='axial')
        self.viewer_frame_layout.addWidget(self.viewports['axial'], 1, 1)

        self.viewports['sagittal'] = ViewPort(self, orientation='sagittal')
        self.viewer_frame_layout.addWidget(self.viewports['sagittal'], 1, 0)

        self.viewports['coronal'] = ViewPort(self, orientation='coronal')
        self.viewer_frame_layout.addWidget(self.viewports['coronal'], 2, 0)

        self.fourth_view = Fourthview(self)
        self.viewer_frame_layout.addWidget(self.fourth_view, 2, 1)

        # Connect crosshair signals
        for vp in self.viewports.values():
            vp.img_label.crosshair_clicked.connect(self._on_crosshair_moved)

        # Initial display
        self._update_all_views()
    

    def _set_base_view(self, view):
        self.base_view_to4th = view
        self.tool_button.setText(view)
        

    def _show_oblique(self):
        if self.oblique_action.isChecked() == False:
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
        else:
            self.tool_button.setEnabled(True)
            self.tool_button.setStyleSheet("color: #E0E0E0;")
            self.outline_action.setChecked(False)
        

    def _show_outline(self):
        if self.outline_action.isChecked() == False:
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
        else:
            self.tool_button.setEnabled(True)
            self.tool_button.setStyleSheet("color: #E0E0E0;")
            self.oblique_action.setChecked(False)



    def _voxel_to_world(self, voxel):
        """Convert voxel coordinates to world coordinates"""
        v = np.append(voxel[:3], 1.0)
        w = self.affine @ v
        return w[:3]

    def _world_to_voxel(self, world):
        """Convert world coordinates to voxel coordinates"""
        w = np.append(world[:3], 1.0)
        v = self.inv_affine @ w
        return v[:3]

    def _clamp_voxel(self, voxel):
        """Clamp voxel to valid array bounds"""
        return np.clip(voxel, 0, np.array(self.data.shape) - 1)

    def _on_crosshair_moved(self, viewport, image_x, image_y):
        """Handle crosshair movement from any viewport"""
        # Only process if crosshair is enabled
        if not self.crosshair_enabled:
            return
            
        # Convert image coordinates to voxel coordinates
        voxel = viewport.image_coords_to_voxel(image_x, image_y)
        
        # Update cursor position
        self.cursor_voxel = self._clamp_voxel(voxel)
        self.cursor_world = self._voxel_to_world(self.cursor_voxel)
        
        # Update ROI position
        if self.roi_enabled:
            roi_size = (self.roi_end - self.roi_start)
            center = self.cursor_voxel
            
            # Update ROI bounds around new center
            self.roi_start = np.array([
                max(0, int(center[0] - roi_size[0]/2)),
                max(0, int(center[1] - roi_size[1]/2)),
                max(0, int(center[2] - roi_size[2]/2))
            ])
            
            self.roi_end = np.array([
                min(self.data.shape[0]-1, int(center[0] + roi_size[0]/2)),
                min(self.data.shape[1]-1, int(center[1] + roi_size[1]/2)),
                min(self.data.shape[2]-1, int(center[2] + roi_size[2]/2))
            ])

        
        # Update sliders in each view to match new cursor position
        self.viewports['axial'].side_bar.setValue(int(round(self.cursor_voxel[2])))
        self.viewports['sagittal'].side_bar.setValue(int(round(self.cursor_voxel[0])))
        self.viewports['coronal'].side_bar.setValue(int(round(self.cursor_voxel[1])))
        
        # Update all views
        self._update_all_views()

    def _update_all_views(self):
        """Update all viewports with current cursor position"""
        i, j, k = self.cursor_voxel
        
        # Update each viewport
        self.viewports['axial'].update_view(int(round(k)), self.cursor_voxel)
        self.viewports['sagittal'].update_view(int(round(i)), self.cursor_voxel)
        self.viewports['coronal'].update_view(int(round(j)), self.cursor_voxel)

    def _toggle_axes(self, checked):
        """Toggle crosshair display and interaction"""
        self.crosshair_enabled = checked
        for viewport in self.viewports.values():
            viewport.img_label.show_crosshair = checked
            viewport.img_label.update()

    def _toggle_roi(self, checked):
        """Toggle ROI display"""
        self.roi_enabled = checked
        # Update ROI state and force view refresh
        for viewport in self.viewports.values():
            viewport.img_label.show_roi = checked
            viewport.update_view(viewport.current_slice, self.cursor_voxel)  # Force full update

    def get_roi_coordinates(self) -> dict:
        """Get ROI bounding box in voxel coordinates 
        Returns:
            dict: A dictionary containing:
                - 'start': starting coordinates [i,j,k]
                - 'end': ending coordinates [i,j,k]
                - 'shape': shape of the ROI [di,dj,dk]
                Returns None if ROI is not enabled.
            """
        
        if not self.roi_enabled:
            return None
        
        return {
            'start': self.roi_start.astype(int),
            'end': self.roi_end.astype(int),
            'shape': (self.roi_end - self.roi_start).astype(int)
        }
        
    def extract_roi_data(self) -> dict:
        """Extract the ROI data from the volume
        Returns:
            dict: A dictionary containing:
                - 'data': numpy array containing the ROI data
                - 'start': starting coordinates [i,j,k]
                - 'end': ending coordinates [i,j,k]
                - 'shape': shape of the ROI [di,dj,dk]
                - 'world_start': starting coordinates in world space
                - 'world_end': ending coordinates in world space
                - 'affine': affine transformation matrix
        Returns None if ROI is not enabled.
        """
        if not self.roi_enabled:
            return None
            
        # Get integer coordinates for slicing
        start_idx = np.floor(self.roi_start).astype(int)
        end_idx = np.ceil(self.roi_end).astype(int)
        
        # Extract the ROI data
        roi_data = self.data[
            start_idx[0]:end_idx[0],
            start_idx[1]:end_idx[1],
            start_idx[2]:end_idx[2]
        ]
        
        # Get world coordinates of ROI bounds
        world_start = self._voxel_to_world(self.roi_start)
        world_end = self._voxel_to_world(self.roi_end)
        
        return {
            'data': roi_data,
            'start': start_idx,
            'end': end_idx,
            'shape': roi_data.shape,
            'world_start': world_start,
            'world_end': world_end,
            'affine': self.affine
        }


class ImageLabel(QLabel):
    crosshair_clicked = Signal(object, float, float)  # viewport, x, y
    
    def __init__(self, viewport, orientation):
        super().__init__(viewport)
        self.viewport = viewport
        self.orientation = orientation
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: none; background-color: black;")
        
        self.show_crosshair = False
        self.show_roi = False
        self.dragging = False
        self.roi_dragging = False
        self.roi_resizing = False
        self.roi_edge = None  # 'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW'
        self.last_mouse_pos = None
        
        # ROI edge detection margin
        self.edge_margin = 5  # pixels
        
        # Enable mouse tracking
        self.setMouseTracking(True)

    def get_pixmap_rect(self):
        """Get the rectangle where the pixmap is drawn"""
        pixmap = self.pixmap()
        if not pixmap:
            return QRect()
        
        # Calculate centered position
        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2
        return QRect(x, y, pixmap.width(), pixmap.height())

    def widget_to_image_coords(self, widget_pos):
        """Convert widget coordinates to image pixel coordinates"""
        pixmap_rect = self.get_pixmap_rect()
        if pixmap_rect.isNull():
            return None, None
        
        # Get position relative to pixmap
        rel_x = widget_pos.x() - pixmap_rect.x()
        rel_y = widget_pos.y() - pixmap_rect.y()
        
        # Check if inside pixmap
        if 0 <= rel_x < pixmap_rect.width() and 0 <= rel_y < pixmap_rect.height():
            return float(rel_x), float(rel_y)
        return None, None

    def is_near_roi_edge(self, pos):
        """Check if position is near ROI edge and return edge type"""
        if not self.show_roi or not hasattr(self.viewport, 'roi_rect'):
            return None
            
        x1, y1, x2, y2 = self.viewport.roi_rect
        if None in (x1, y1, x2, y2):
            return None
            
        pixmap_rect = self.get_pixmap_rect()
        mouse_x = pos.x() - pixmap_rect.x()
        mouse_y = pos.y() - pixmap_rect.y()
        
        near_left = abs(mouse_x - x1) < self.edge_margin
        near_right = abs(mouse_x - x2) < self.edge_margin
        near_top = abs(mouse_y - y1) < self.edge_margin
        near_bottom = abs(mouse_y - y2) < self.edge_margin
        
        if near_top and near_left: return 'NW'
        if near_top and near_right: return 'NE'
        if near_bottom and near_left: return 'SW'
        if near_bottom and near_right: return 'SE'
        if near_top: return 'N'
        if near_bottom: return 'S'
        if near_left: return 'W'
        if near_right: return 'E'
        
        # Check if inside ROI
        if x1 <= mouse_x <= x2 and y1 <= mouse_y <= y2:
            return 'INSIDE'
            
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            img_x, img_y = self.widget_to_image_coords(event.pos())
            if img_x is None:
                return
                
            edge_type = self.is_near_roi_edge(event.pos())
            
            if self.viewport.manager.roi_enabled and edge_type:
                if edge_type == 'INSIDE':
                    self.roi_dragging = True
                else:
                    self.roi_resizing = True
                    self.roi_edge = edge_type
                self.last_mouse_pos = event.pos()
            elif self.viewport.manager.crosshair_enabled:
                self.dragging = True
                self.crosshair_clicked.emit(self.viewport, img_x, img_y)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.roi_dragging or self.roi_resizing:
            current_pos = event.pos()
            if self.last_mouse_pos is None:
                self.last_mouse_pos = current_pos
                return
                
            dx = current_pos.x() - self.last_mouse_pos.x()
            dy = current_pos.y() - self.last_mouse_pos.y()
            
            if self.roi_dragging:
                self.viewport.move_roi(dx, dy)
            else:
                self.viewport.resize_roi(dx, dy, self.roi_edge)
                
            self.last_mouse_pos = current_pos
            
        elif self.dragging and self.viewport.manager.crosshair_enabled:
            img_x, img_y = self.widget_to_image_coords(event.pos())
            if img_x is not None:
                self.crosshair_clicked.emit(self.viewport, img_x, img_y)
        else:
            # Update cursor based on ROI edge proximity
            if self.viewport.manager.roi_enabled:
                edge_type = self.is_near_roi_edge(event.pos())
                if edge_type in ('N', 'S'):
                    self.setCursor(Qt.SizeVerCursor)
                elif edge_type in ('E', 'W'):
                    self.setCursor(Qt.SizeHorCursor)
                elif edge_type in ('NW', 'SE'):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif edge_type in ('NE', 'SW'):
                    self.setCursor(Qt.SizeBDiagCursor)
                elif edge_type == 'INSIDE':
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.roi_dragging = False
            self.roi_resizing = False
            self.roi_edge = None
            self.last_mouse_pos = None

    def paintEvent(self, event):
        """Draw image + overlays"""
        super().paintEvent(event)
        
        pixmap = self.pixmap()
        if not pixmap:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pixmap_rect = self.get_pixmap_rect()
        
        # Draw crosshair
        if self.show_crosshair and hasattr(self.viewport, 'crosshair_pos'):
            cx, cy = self.viewport.crosshair_pos
            if cx is not None and cy is not None:
                # Get colors based on orientation and control function
                if self.orientation == "axial":
                    v_color = QColor(0, 255, 0)  # Green vertical line controls sagittal
                    h_color = QColor(0, 0, 255)  # Blue horizontal line controls coronal
                elif self.orientation == "sagittal":
                    v_color = QColor(0, 0, 255)  # Blue vertical line controls coronal
                    h_color = QColor(255, 255, 0)  # Yellow horizontal line controls axial
                elif self.orientation == "coronal":
                    v_color = QColor(0, 255, 0)  # Green vertical line controls sagittal
                    h_color = QColor(255, 255, 0)  # Yellow horizontal line controls axial
            
                else:
                    v_color = h_color = QColor(255, 255, 255)
                
                # Convert to widget coordinates
                screen_x = pixmap_rect.x() + cx
                screen_y = pixmap_rect.y() + cy
                
                # Draw vertical line
                pen = QPen(v_color, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(int(screen_x), pixmap_rect.top(), 
                               int(screen_x), pixmap_rect.bottom())
                
                # Draw horizontal line
                pen = QPen(h_color, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(pixmap_rect.left(), int(screen_y), 
                               pixmap_rect.right(), int(screen_y))
        
        # Draw ROI box
        if self.show_roi and hasattr(self.viewport, 'roi_rect'):
            x1, y1, x2, y2 = self.viewport.roi_rect
            if None not in (x1, y1, x2, y2):
                # Use semi-transparent red for ROI
                pen = QPen(QColor(255, 0, 0, 200), 2, Qt.SolidLine)
                painter.setPen(pen)
                
                # Convert to widget coordinates
                screen_x1 = pixmap_rect.x() + x1
                screen_y1 = pixmap_rect.y() + y1
                screen_x2 = pixmap_rect.x() + x2
                screen_y2 = pixmap_rect.y() + y2
                
                # Draw the ROI box with dashed lines
                pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
                painter.drawRect(int(screen_x1), int(screen_y1), 
                               int(screen_x2 - screen_x1), int(screen_y2 - screen_y1))
        
        painter.end()


class ViewPort(QFrame):
    def __init__(self, manager, orientation=None):
        super().__init__()
        
        self.manager = manager
        self.orientation = orientation
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QFrame {
                border-radius: 0px;
                background-color: black;
                border: 1px solid #444;
            }""")
        
        self.viewport_layout = QHBoxLayout(self)
        self.viewport_layout.setContentsMargins(0, 0, 0, 0)
        self.viewport_layout.setSpacing(0)
        
        # Get data references
        self.data = self.manager.data
        self.header = self.manager.nifti_file.header
        self.pixdim = self.header['pixdim'][1:4]
        
        # Determine slice range
        if orientation == 'axial':
            self.max_slices = self.data.shape[2]
            self.current_slice = self.max_slices // 2
        elif orientation == 'sagittal':
            self.max_slices = self.data.shape[0]
            self.current_slice = self.max_slices // 2
        elif orientation == 'coronal':
            self.max_slices = self.data.shape[1]
            self.current_slice = self.max_slices // 2
        else:
            self.max_slices = 1
            self.current_slice = 0
        
        # Create image label
        self.img_label = ImageLabel(self, orientation)
        
        # Scrollbar
        self.side_bar = NavBar(self, self.current_slice, self.max_slices)
        
        self.viewport_layout.addWidget(self.side_bar)
        self.viewport_layout.addWidget(self.img_label)
        
        # Crosshair and ROI positions (in image pixel coordinates)
        self.crosshair_pos = (None, None)
        self.roi_rect = (None, None, None, None)
        
        # Store transformation info for coordinate mapping
        self.slice_shape_before_transform = None
        self.slice_shape_after_transform = None
        self.scale_factor = (1.0, 1.0)
        
        # Initial display
        self.display_slice(self.current_slice)

        # Put Anatomical positions labels
        if self.orientation == "axial":
            self.labels = {
                "top": QLabel("A", self),
                "bottom": QLabel("P", self),
                "left": QLabel("R", self),
                "right": QLabel("L", self),
            }
        elif self.orientation == "sagittal":
            self.labels = {
                "top": QLabel("S", self),
                "bottom": QLabel("I", self),
                "left": QLabel("A", self),
                "right": QLabel("P", self),
            }
        elif self.orientation == "coronal":
            self.labels = {
                "top": QLabel("S", self),
                "bottom": QLabel("I", self),
                "left": QLabel("R", self),
                "right": QLabel("L", self),
            }

        # Style all labels to appear bright and clear
        for lbl in self.labels.values():
            lbl.setStyleSheet("""
                color: yellow;
                font: bold 16px 'Arial';
                background: transparent;
                border: none;
            """)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.raise_()  # ensure on top of image
        self._draw_anatomical_lables(None)  # Initial positioning

    def _draw_anatomical_lables(self, event):
        """Keep image and labels correctly positioned"""
        w, h = self.width(), self.height()
        margin = 10

        # Image fills the entire frame
        self.img_label.setGeometry(0, 0, w, h)

        # Center the labels around the frame edges
        for lbl in self.labels.values():
            lbl.adjustSize()
    
        self.labels["top"].move(w // 2, margin)
        self.labels["bottom"].move(w  // 2, h - self.labels["bottom"].height() - margin)
        self.labels["left"].move(margin + self.side_bar.width(), (h - self.labels["left"].height()) // 2)
        self.labels["right"].move(w - self.labels["right"].width() - margin, (h - self.labels["right"].height()) // 2)




    def get_aspect_ratio(self):
        """Calculate physical aspect ratio"""
        if self.orientation == 'axial':
            return self.pixdim[0] / self.pixdim[1]
        elif self.orientation == 'sagittal':
            return self.pixdim[1] / self.pixdim[2]
        elif self.orientation == 'coronal':
            return self.pixdim[0] / self.pixdim[2]
        return 1.0

    def display_slice(self, slice_index):
        """Display a specific slice"""
        if slice_index < 0 or slice_index >= self.max_slices:
            return
        
        self.current_slice = slice_index
        
        # Extract slice
        if self.orientation == 'axial':
            slice_data = self.data[:, :, slice_index]
        elif self.orientation == 'sagittal':
            slice_data = self.data[slice_index, :, :]
        elif self.orientation == 'coronal':
            slice_data = self.data[:, slice_index, :]
        else:
            return
        
        # Store original shape BEFORE any transformations
        self.slice_shape_before_transform = slice_data.shape  # (height, width) or (rows, cols)
        
        # Normalize
        slice_min, slice_max = np.min(slice_data), np.max(slice_data)
        if slice_max > slice_min:
            img = ((slice_data - slice_min) / (slice_max - slice_min) * 255).astype(np.uint8)
        else:
            img = np.zeros_like(slice_data, dtype=np.uint8)
        
        # Apply rotation/flip
        img = np.rot90(img, k=1)
        if self.orientation == "axial":
            img = np.flip(img)
        elif self.orientation == "coronal":
            img = np.fliplr(img)
        
        # Store shape AFTER transformations
        self.slice_shape_after_transform = img.shape  # This is what gets displayed
        
        img = np.ascontiguousarray(img)
        
        # Create QImage
        height, width = img.shape
        q_image = QImage(img.data, width, height, width, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        
        # Scale with aspect ratio
        aspect_ratio = self.get_aspect_ratio()
        available_width = self.width() - 20
        available_height = self.height() - 20
        
        if available_width / available_height > aspect_ratio:
            target_height = available_height
            target_width = int(target_height * aspect_ratio)
        else:
            target_width = available_width
            target_height = int(target_width / aspect_ratio)
        
        # Adjust for non-square voxels
        if self.orientation in ["coronal", "sagittal"]:
            target_width = target_height
        
        scaled_pixmap = pixmap.scaled(
            target_width, target_height,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Store scale factor
        self.scale_factor = (
            scaled_pixmap.width() / width,
            scaled_pixmap.height() / height
        )
        
        self.img_label.setPixmap(scaled_pixmap)

    def update_view(self, slice_index, cursor_voxel):
        """Update view with new slice and crosshair position"""
        self.display_slice(slice_index)
        self.side_bar.setValue(slice_index)
        
        # Update crosshair position
        self.crosshair_pos = self.voxel_to_image_coords(cursor_voxel)
        
        # Update ROI rectangle
        if hasattr(self.manager, 'roi_enabled') and self.manager.roi_enabled:
            self.roi_rect = self.get_roi_in_image_coords()
        else:
            self.roi_rect = (None, None, None, None)
        
        # Force update of the display
        self.img_label.update()

    def voxel_to_image_coords(self, voxel):
        """Convert 3D voxel coordinates to 2D image pixel coordinates (in displayed pixmap space)"""
        i, j, k = voxel
        
        if self.slice_shape_after_transform is None:
            return (None, None)
        
        pixmap = self.img_label.pixmap()
        if not pixmap:
            return (None, None)
        
        # Map voxel to image coordinates maintaining anatomical orientation
        if self.orientation == 'axial':
            # For axial view (superior view)
            # x increases from right to left (patient's right to left)
            # y increases from anterior to posterior
            x_in_transformed = self.slice_shape_before_transform[0] - 1 - i  # Reverse left-right
            y_in_transformed = j
            
        elif self.orientation == 'sagittal':
            # For sagittal view (looking from patient's right/left)
            # x increases from anterior to posterior
            # y increases from inferior to superior
            x_in_transformed = j
            y_in_transformed = self.slice_shape_before_transform[1] - 1 - k  # Reverse superior-inferior
            
        elif self.orientation == 'coronal':
            # For coronal view (looking from anterior/posterior)
            # x increases from right to left (patient's right to left)
            # y increases from superior to inferior
            x_in_transformed = self.slice_shape_before_transform[0] - 1 - i
            y_in_transformed = self.slice_shape_before_transform[1] - 1 - k  # Reverse superior-inferior
        else:
            return (None, None)
        
        # Scale to displayed pixmap size
        x_display = x_in_transformed * self.scale_factor[0]
        y_display = y_in_transformed * self.scale_factor[1]
        
        return (x_display, y_display)

    def image_coords_to_voxel(self, img_x, img_y):
        """Convert 2D image coordinates (in displayed pixmap) to 3D voxel coordinates"""
        if self.slice_shape_after_transform is None:
            return self.manager.cursor_voxel
        
        # Unscale from displayed size to image size
        x_transformed = img_x / self.scale_factor[0]
        y_transformed = img_y / self.scale_factor[1]
        
        # Convert back to voxel coordinates maintaining anatomical orientation
        if self.orientation == 'axial':
            # Axial view conversion
            i = self.slice_shape_before_transform[0] - 1 - x_transformed  # Reverse left-right
            j = y_transformed
            k = self.current_slice
            
        elif self.orientation == 'sagittal':
            # Sagittal view conversion
            i = self.current_slice
            j = x_transformed
            k = self.slice_shape_before_transform[1] - 1 - y_transformed  # Reverse superior-inferior
            
        elif self.orientation == 'coronal':
            # Coronal view conversion
            i = self.slice_shape_before_transform[0] - 1 - x_transformed
            j = self.current_slice
            k = self.slice_shape_before_transform[1] - 1 - y_transformed  # Reverse superior-inferior
        else:
            return self.manager.cursor_voxel
        
        return np.array([i, j, k])

    def get_roi_in_image_coords(self):
        """Convert ROI voxel bounds to image pixel coordinates"""
        if not self.manager.roi_enabled:
            return (None, None, None, None)
        
        roi_start = self.manager.roi_start.copy()
        roi_end = self.manager.roi_end.copy()
        
        # Check if current slice intersects with ROI
        if self.orientation == 'axial':
            if not (roi_start[2] <= self.current_slice <= roi_end[2]):
                return (None, None, None, None)
            corners = [
                [roi_start[0], roi_start[1], self.current_slice],
                [roi_end[0], roi_end[1], self.current_slice]
            ]
        elif self.orientation == 'sagittal':
            if not (roi_start[0] <= self.current_slice <= roi_end[0]):
                return (None, None, None, None)
            corners = [
                [self.current_slice, roi_start[1], roi_start[2]],
                [self.current_slice, roi_end[1], roi_end[2]]
            ]
        elif self.orientation == 'coronal':
            if not (roi_start[1] <= self.current_slice <= roi_end[1]):
                return (None, None, None, None)
            corners = [
                [roi_start[0], self.current_slice, roi_start[2]],
                [roi_end[0], self.current_slice, roi_end[2]]
            ]
        else:
            return (None, None, None, None)
        
        # Convert corners to image coordinates
        pos1 = self.voxel_to_image_coords(np.array(corners[0]))
        pos2 = self.voxel_to_image_coords(np.array(corners[1]))
        
        if None in pos1 or None in pos2:
            return (None, None, None, None)
        
        # Ensure correct ordering of coordinates
        x1, y1 = min(pos1[0], pos2[0]), min(pos1[1], pos2[1])
        x2, y2 = max(pos1[0], pos2[0]), max(pos1[1], pos2[1])
        
        return (x1, y1, x2, y2)

    def move_roi(self, dx, dy):
        """Move ROI by pixel delta in current view"""
        if not self.manager.roi_enabled:
            return
            
        # Convert pixel deltas to voxel coordinates based on orientation
        scale_x = self.scale_factor[0]
        scale_y = self.scale_factor[1]
        
        voxel_dx = dx / scale_x
        voxel_dy = dy / scale_y
        
        # Calculate ROI size to maintain
        roi_size = self.manager.roi_end - self.manager.roi_start
        
        # Update ROI bounds based on orientation
        if self.orientation == 'axial':
            delta_i = voxel_dx  # Moving right increases i
            delta_j = voxel_dy  # Moving down increases j
            
            new_start = self.manager.roi_start.copy()
            new_start[0] -= delta_i
            new_start[1] += delta_j
            
        elif self.orientation == 'sagittal':
            delta_j = voxel_dx  # Moving right increases j
            delta_k = -voxel_dy  # Moving up increases k
            
            new_start = self.manager.roi_start.copy()
            new_start[1] += delta_j
            new_start[2] += delta_k
            
        elif self.orientation == 'coronal':
            delta_i = voxel_dx  # Moving right increases i
            delta_k = -voxel_dy  # Moving up increases k
            
            new_start = self.manager.roi_start.copy()
            new_start[0] -= delta_i
            new_start[2] += delta_k
            
        # Clamp new position to valid bounds
        shape = np.array(self.data.shape)
        new_start = np.clip(new_start, 0, shape - roi_size)
        new_end = new_start + roi_size
        
        # Update ROI bounds
        self.manager.roi_start = new_start
        self.manager.roi_end = new_end
        
        # Update display
        self.manager._update_all_views()

    def resize_roi(self, dx, dy, edge):
        """Resize ROI by dragging an edge or corner"""
        if not self.manager.roi_enabled:
            return
            
        # Convert pixel deltas to voxel coordinates
        scale_x = self.scale_factor[0]
        scale_y = self.scale_factor[1]
        
        voxel_dx = dx / scale_x
        voxel_dy = dy / scale_y
        
        # Update ROI bounds based on orientation and edge being dragged
        if self.orientation == 'axial':
            if 'N' in edge: self.manager.roi_start[1] += voxel_dy
            if 'S' in edge: self.manager.roi_end[1] += voxel_dy
            if 'W' in edge: self.manager.roi_end[0] -= voxel_dx
            if 'E' in edge: self.manager.roi_start[0] -= voxel_dx
        elif self.orientation == 'sagittal':
            if 'N' in edge: self.manager.roi_end[2] -= voxel_dy
            if 'S' in edge: self.manager.roi_start[2] -= voxel_dy
            if 'W' in edge: self.manager.roi_start[1] += voxel_dx
            if 'E' in edge: self.manager.roi_end[1] += voxel_dx
        elif self.orientation == 'coronal':
            if 'S' in edge: self.manager.roi_start[2] -= voxel_dy
            if 'N' in edge: self.manager.roi_end[2] -= voxel_dy
            if 'W' in edge: self.manager.roi_end[0] -= voxel_dx
            if 'E' in edge: self.manager.roi_start[0] -= voxel_dx
            
        # Ensure ROI maintains positive size
        for i in range(3):
            if self.manager.roi_start[i] > self.manager.roi_end[i]:
                self.manager.roi_start[i], self.manager.roi_end[i] = self.manager.roi_end[i], self.manager.roi_start[i]
            
        # Clamp ROI to image bounds
        shape = self.data.shape
        self.manager.roi_start = np.clip(self.manager.roi_start, 0, shape)
        self.manager.roi_end = np.clip(self.manager.roi_end, 0, shape)
        
        # Update display
        self.manager._update_all_views()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'current_slice'):
            # Redisplay and update crosshair
            self.display_slice(self.current_slice)
            if hasattr(self.manager, 'cursor_voxel'):
                self.crosshair_pos = self.voxel_to_image_coords(self.manager.cursor_voxel)
                self.roi_rect = self.get_roi_in_image_coords()
                self.img_label.update()
        self._draw_anatomical_lables(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta < 0 and self.current_slice < self.max_slices - 1:
            new_slice = self.current_slice + 1
        elif delta > 0 and self.current_slice > 0:
            new_slice = self.current_slice - 1
        else:
            return
        
        # Update the slice and ensure ROI updates
        self.current_slice = new_slice
        self.side_bar.setValue(new_slice)
        
        # Force full view update including ROI
        self.update_view(new_slice, self.manager.cursor_voxel)


class NavBar(QFrame):
    def __init__(self, viewport=None, slice_idx=1, total_slices=None):
        super().__init__()
        self.viewport = viewport
        self.slice_idx = slice_idx
        self.total_slices = total_slices
        
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.scrollbar = QScrollBar(Qt.Vertical, self)
        self.scrollbar.setStyleSheet("""
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 14px;
                margin: 16px 0 16px 0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #888;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #aaa;
            }
            QScrollBar::sub-line:vertical {
                background: #444;
                height: 16px;
                subcontrol-origin: margin;
                subcontrol-position: top;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QScrollBar::sub-line:vertical:hover {
                background: #666;
            }
            QScrollBar::add-line:vertical {
                background: #444;
                height: 16px;
                subcontrol-origin: margin;
                subcontrol-position: bottom;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QScrollBar::add-line:vertical:hover {
                background: #666;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        self.scrollbar.setRange(0, total_slices - 1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(slice_idx)
        
        # Update handler for scrollbar to ensure ROI and crosshair updates
        def on_scroll_value_changed(value):
            self.viewport.current_slice = value
            
            # Update cursor voxel position for the current orientation
            new_cursor = self.viewport.manager.cursor_voxel.copy()
            if self.viewport.orientation == 'axial':
                new_cursor[2] = value
            elif self.viewport.orientation == 'sagittal':
                new_cursor[0] = value
            elif self.viewport.orientation == 'coronal':
                new_cursor[1] = value
                
            # Update cursor position and all views
            self.viewport.manager.cursor_voxel = new_cursor
            self.viewport.manager.cursor_world = self.viewport.manager._voxel_to_world(new_cursor)
            self.viewport.manager._update_all_views()
            
        self.scrollbar.valueChanged.connect(on_scroll_value_changed)
        
        layout.addWidget(self.scrollbar)

    def setValue(self, slice_idx):
        self.scrollbar.blockSignals(True)
        self.scrollbar.setValue(slice_idx)
        self.scrollbar.blockSignals(False)


class Fourthview(QFrame):
    def __init__(self, parent=None, mode="oblique", segmentation_mask=None, oblique_data=[]):
        super().__init__(parent)
        self.mode = mode
        self.segmentation_mask = segmentation_mask
        self.oblique_data = oblique_data

    def set_mode(self, mode):
        self.mode = mode
        self.update_view()

    def update_view(self):
        if self.mode == "oblique":
            img = self.oblique_slice
        elif self.mode == "outline" and self.segmentation_mask is not None:
            img = self.extract_outline(self.segmentation_mask)
        else:
            img = np.zeros((256,256))  # fallback blank
        self.display_image(img)

    def extract_outline(self, mask):
        import cv2, numpy as np
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        outline = np.zeros_like(mask)
        cv2.drawContours(outline, contours, -1, color=255, thickness=1)
        return outline

    