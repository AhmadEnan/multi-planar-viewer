from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QPointF, QTimer
from PySide6.QtGui import *
import nibabel as nib
import numpy as np
import cv2
from scipy.ndimage import map_coordinates


class ViewerManager(QFrame):
    def __init__(self, loaded_nifti=None):
        super().__init__()

        self.nifti_file = loaded_nifti
        self.fourth_view_mode = None
        self.segmentation_mask = r"test_data/segmentations\liver.nii.gz"
        
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
        self.oblique_action.setToolTip("Display oblique in the 4th view")
        self.oblique_action.triggered.connect(self._show_oblique)
        self.toolbar.addAction(self.oblique_action)
        self.oblique_action.setCheckable(True)

        outline_icon = QIcon(r"icons/outline_icon.png")
        self.outline_action = QAction(outline_icon, "Show outline view", self)
        self.outline_action.setToolTip("Display the organ outline in the 4th view")
        self.outline_action.triggered.connect(self._show_outline)
        self.toolbar.addAction(self.outline_action)
        self.outline_action.setCheckable(True)

        # Drop down to choose the required view
        self.base_view_to4th = "axial"
        self.tool_button = QToolButton(self)
        self.tool_button.setToolTip("Choose a Base view to make the fourth view on it")
        self.tool_button.setText(self.base_view_to4th)
        self.tool_button.setStyleSheet("color: grey;")
        self.tool_button.setEnabled(False)
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
        self.tool_button.setPopupMode(QToolButton.MenuButtonPopup)

        self.toolbar.addSeparator()
        self.viewer_frame_layout.addWidget(self.toolbar, 0, 0, 1, 2)

        # Preprocessing NIFTI data
        self.img_ras = nib.as_closest_canonical(self.nifti_file)
        self.affine = self.img_ras.affine
        self.inv_affine = np.linalg.inv(self.affine)
        
        self.data = self.img_ras.get_fdata()
        shape = np.array(self.data.shape)
        
        # Initialize cursor at center (in voxel coordinates)
        self.cursor_voxel = (shape - 1) / 2
        self.cursor_world = self._voxel_to_world(self.cursor_voxel)

        # Control flags
        self.crosshair_enabled = False
        self.roi_enabled = False

        # ROI bounds (in voxel coordinates)
        roi_size = shape / 3
        center = self.cursor_voxel.copy()
        
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
        
        # Ensure ROI has minimum size
        min_size = 10
        for i in range(3):
            if self.roi_end[i] - self.roi_start[i] < min_size:
                center_i = (self.roi_start[i] + self.roi_end[i]) // 2
                self.roi_start[i] = max(0, center_i - min_size//2)
                self.roi_end[i] = min(shape[i]-1, center_i + min_size//2)

        # Oblique line parameters (normalized 0-1 coordinates relative to base view)
        self.oblique_line = {
            'x1': 0.3, 'y1': 0.5,
            'x2': 0.7, 'y2': 0.5,
            'angle': 0.0
        }

        # Create viewports
        self.viewports = {}
        
        self.viewports['axial'] = ViewPort(self, orientation='axial')
        self.viewer_frame_layout.addWidget(self.viewports['axial'], 1, 1)

        self.viewports['sagittal'] = ViewPort(self, orientation='sagittal')
        self.viewer_frame_layout.addWidget(self.viewports['sagittal'], 1, 0)

        self.viewports['coronal'] = ViewPort(self, orientation='coronal')
        self.viewer_frame_layout.addWidget(self.viewports['coronal'], 2, 0)

        self.fourth_view = FourthView(self)
        self.viewer_frame_layout.addWidget(self.fourth_view, 2, 1)

        # Connect crosshair signals
        for vp in self.viewports.values():
            vp.img_label.crosshair_clicked.connect(self._on_crosshair_moved)

        # Initial display
        self._update_all_views()
    
    def _set_base_view(self, view):
        self.base_view_to4th = view
        self.tool_button.setText(view)
        self._update_oblique_display()

    def _show_oblique(self):
        if not self.oblique_action.isChecked():
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
            self.fourth_view_mode = None
            # Hide oblique line in all views
            for viewport in self.viewports.values():
                viewport.img_label.show_oblique_line = False
                viewport.update()
        else:
            self.tool_button.setEnabled(True)
            self.tool_button.setStyleSheet("color: #E0E0E0;")
            self.outline_action.setChecked(False)
            self.axis_action.setChecked(False)
            self.roi_action.setChecked(False)
            self._toggle_axes(False)
            self._toggle_roi(False)
            self.fourth_view_mode = "oblique"
            # Show oblique line only in base view
            base_view = self.base_view_to4th
            for view_name, viewport in self.viewports.items():
                viewport.img_label.show_oblique_line = (view_name == base_view)
                viewport.update()
        
        self._update_oblique_display()

    def _show_outline(self):
        if not self.outline_action.isChecked():
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
            self.fourth_view_mode = None
        else:
            self.tool_button.setEnabled(True)
            self.tool_button.setStyleSheet("color: #E0E0E0;")
            self.oblique_action.setChecked(False)
            self.axis_action.setChecked(False)
            self.roi_action.setChecked(False)
            self._toggle_axes(False)
            self._toggle_roi(False)
            self.fourth_view_mode = "outline"
        
        self._update_oblique_display()

    def _update_oblique_display(self):
        """Update the base view and fourth view when oblique parameters change"""
        # Update base view to show oblique line
        for view in self.viewports.values():
            view.update_oblique_line()

        # Update fourth view
        self.fourth_view.update_view()

    def _voxel_to_world(self, voxel):
        v = np.append(voxel[:3], 1.0)
        w = self.affine @ v
        return w[:3]

    def _world_to_voxel(self, world):
        w = np.append(world[:3], 1.0)
        v = self.inv_affine @ w
        return v[:3]

    def _clamp_voxel(self, voxel):
        return np.clip(voxel, 0, np.array(self.data.shape) - 1)

    def _on_crosshair_moved(self, viewport, image_x, image_y):
        if not self.crosshair_enabled:
            return
            
        voxel = viewport.image_coords_to_voxel(image_x, image_y)
        self.cursor_voxel = self._clamp_voxel(voxel)
        self.cursor_world = self._voxel_to_world(self.cursor_voxel)
        
        if self.roi_enabled:
            roi_size = (self.roi_end - self.roi_start)
            center = self.cursor_voxel
            
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
        
        self.viewports['axial'].side_bar.setValue(int(round(self.cursor_voxel[2])))
        self.viewports['sagittal'].side_bar.setValue(int(round(self.cursor_voxel[0])))
        self.viewports['coronal'].side_bar.setValue(int(round(self.cursor_voxel[1])))
        
        self._update_all_views()

    def _update_all_views(self):
        i, j, k = self.cursor_voxel
        
        self.viewports['axial'].update_view(int(round(k)), self.cursor_voxel)
        self.viewports['sagittal'].update_view(int(round(i)), self.cursor_voxel)
        self.viewports['coronal'].update_view(int(round(j)), self.cursor_voxel)

    def _toggle_axes(self, checked):
        self.crosshair_enabled = checked
        if checked:
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
            self.outline_action.setChecked(False)
            self.oblique_action.setChecked(False)

        for viewport in self.viewports.values():
            viewport.img_label.show_crosshair = checked
            viewport.img_label.update()

    def _toggle_roi(self, checked):
        self.roi_enabled = checked
        if checked:
            self.tool_button.setEnabled(False)
            self.tool_button.setStyleSheet("color: grey;")
            self.outline_action.setChecked(False)
            self.oblique_action.setChecked(False)
            
        for viewport in self.viewports.values():
            viewport.img_label.show_roi = checked
            viewport.update_view(viewport.current_slice, self.cursor_voxel)


class ImageLabel(QLabel):
    crosshair_clicked = Signal(object, float, float)
    
    def __init__(self, viewport, orientation):
        super().__init__(viewport)
        self.viewport = viewport
        self.orientation = orientation
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: none; background-color: black;")
        
        self.show_crosshair = False
        self.show_roi = False
        self.show_oblique_line = False
        self.dragging = False
        self.roi_dragging = False
        self.roi_resizing = False
        self.roi_edge = None
        self.last_mouse_pos = None
        
        # Oblique line dragging
        self.oblique_dragging = None  # None, 'line', 'handle1', 'handle2', 'rotate'
        
        self.edge_margin = 5
        self.setMouseTracking(True)

    def get_pixmap_rect(self):
        pixmap = self.pixmap()
        if not pixmap:
            return QRect()
        
        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2
        return QRect(x, y, pixmap.width(), pixmap.height())

    def widget_to_image_coords(self, widget_pos):
        pixmap_rect = self.get_pixmap_rect()
        if pixmap_rect.isNull():
            return None, None
        
        rel_x = widget_pos.x() - pixmap_rect.x()
        rel_y = widget_pos.y() - pixmap_rect.y()
        
        if 0 <= rel_x < pixmap_rect.width() and 0 <= rel_y < pixmap_rect.height():
            return float(rel_x), float(rel_y)
        return None, None

    def is_near_point(self, pos, point, threshold=8):
        """Check if position is near a point"""
        return np.sqrt((pos.x() - point.x())**2 + (pos.y() - point.y())**2) < threshold

    def is_near_line(self, pos, p1, p2, threshold=5):
        """Check if position is near a line segment"""
        x0, y0 = pos.x(), pos.y()
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return False
        
        t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        dist = np.sqrt((x0 - proj_x)**2 + (y0 - proj_y)**2)
        return dist < threshold

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            img_x, img_y = self.widget_to_image_coords(event.pos())
            if img_x is None:
                return
            
            # Check oblique line interaction
            if self.show_oblique_line and hasattr(self.viewport, 'oblique_screen_coords'):
                p1, p2, h1, h2 = self.viewport.oblique_screen_coords
                
                if self.is_near_point(event.pos(), h1):
                    self.oblique_dragging = 'handle1'
                    self.last_mouse_pos = event.pos()
                    self.setCursor(Qt.ClosedHandCursor)
                    return
                elif self.is_near_point(event.pos(), h2):
                    self.oblique_dragging = 'handle2'
                    self.last_mouse_pos = event.pos()
                    self.setCursor(Qt.ClosedHandCursor)
                    return
                elif self.is_near_line(event.pos(), p1, p2):
                    self.oblique_dragging = 'line'
                    self.last_mouse_pos = event.pos()
                    self.setCursor(Qt.SizeAllCursor)
                    return
                else:
                    self.setCursor(Qt.ArrowCursor)
            
            # ROI interaction
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
        # Oblique line dragging
        if self.show_oblique_line:
            if self.oblique_dragging:
                if self.last_mouse_pos is None:
                    self.last_mouse_pos = event.pos()
                    
                
                img_x, img_y = self.widget_to_image_coords(event.pos())
                if img_x is None:
                    return
                
                pixmap = self.pixmap()
                if not pixmap:
                    return
                
                # Normalize coordinates
                norm_x = img_x / pixmap.width()
                norm_y = img_y / pixmap.height()
                
                if self.oblique_dragging == 'handle1':
                    self.viewport.manager.oblique_line['x1'] = np.clip(norm_x, 0, 1)
                    self.viewport.manager.oblique_line['y1'] = np.clip(norm_y, 0, 1)
                    self.viewport.manager._update_oblique_display()
                    self.setCursor(Qt.ClosedHandCursor)
                elif self.oblique_dragging == 'handle2':
                    self.viewport.manager.oblique_line['x2'] = np.clip(norm_x, 0, 1)
                    self.viewport.manager.oblique_line['y2'] = np.clip(norm_y, 0, 1)
                    self.viewport.manager._update_oblique_display()
                    self.setCursor(Qt.ClosedHandCursor)
                elif self.oblique_dragging == 'line':
                    dx = (event.pos().x() - self.last_mouse_pos.x()) / pixmap.width()
                    dy = (event.pos().y() - self.last_mouse_pos.y()) / pixmap.height()
                    
                    self.viewport.manager.oblique_line['x1'] += dx
                    self.viewport.manager.oblique_line['y1'] += dy
                    self.viewport.manager.oblique_line['x2'] += dx
                    self.viewport.manager.oblique_line['y2'] += dy
                    self.setCursor(Qt.SizeAllCursor)


                # Check oblique line interaction
            else:
                p1, p2, h1, h2 = self.viewport.oblique_screen_coords
                if self.is_near_point(event.pos(), h1):
                    self.setCursor(Qt.OpenHandCursor)
                    return
                elif self.is_near_point(event.pos(), h2):
                    self.setCursor(Qt.OpenHandCursor)
                    return
                elif self.is_near_line(event.pos(), p1, p2):
                    self.setCursor(Qt.SizeAllCursor)
                    return
                else:
                    self.setCursor(Qt.ArrowCursor)
                
            # Clamp to bounds
            self.viewport.manager.oblique_line['x1'] = np.clip(self.viewport.manager.oblique_line['x1'], 0, 1)
            self.viewport.manager.oblique_line['y1'] = np.clip(self.viewport.manager.oblique_line['y1'], 0, 1)
            self.viewport.manager.oblique_line['x2'] = np.clip(self.viewport.manager.oblique_line['x2'], 0, 1)
            self.viewport.manager.oblique_line['y2'] = np.clip(self.viewport.manager.oblique_line['y2'], 0, 1)
            
            self.viewport.manager._update_oblique_display()
        
            self.last_mouse_pos = event.pos()

        
        # ROI dragging
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
            # Update cursor
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
            if self.show_oblique_line and self.oblique_dragging != "line":
                self.setCursor(Qt.OpenHandCursor)
            self.oblique_dragging = None
            self.last_mouse_pos = None

    def is_near_roi_edge(self, pos):
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
        
        if x1 <= mouse_x <= x2 and y1 <= mouse_y <= y2:
            return 'INSIDE'
            
        return None

    def paintEvent(self, event):
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
                if self.orientation == "axial":
                    v_color = QColor(0, 255, 0)
                    h_color = QColor(0, 0, 255)
                elif self.orientation == "sagittal":
                    v_color = QColor(0, 0, 255)
                    h_color = QColor(255, 255, 0)
                elif self.orientation == "coronal":
                    v_color = QColor(0, 255, 0)
                    h_color = QColor(255, 255, 0)
                else:
                    v_color = h_color = QColor(255, 255, 255)
                
                screen_x = pixmap_rect.x() + cx
                screen_y = pixmap_rect.y() + cy
                
                pen = QPen(v_color, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(int(screen_x), pixmap_rect.top(), 
                               int(screen_x), pixmap_rect.bottom())
                
                pen = QPen(h_color, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(pixmap_rect.left(), int(screen_y), 
                               pixmap_rect.right(), int(screen_y))
        
        # Draw ROI box
        if self.show_roi and hasattr(self.viewport, 'roi_rect'):
            x1, y1, x2, y2 = self.viewport.roi_rect
            if None not in (x1, y1, x2, y2):
                pen = QPen(QColor(255, 0, 0, 200), 2, Qt.DashLine)
                painter.setPen(pen)
                
                screen_x1 = pixmap_rect.x() + x1
                screen_y1 = pixmap_rect.y() + y1
                screen_x2 = pixmap_rect.x() + x2
                screen_y2 = pixmap_rect.y() + y2
                
                painter.drawRect(int(screen_x1), int(screen_y1), 
                               int(screen_x2 - screen_x1), int(screen_y2 - screen_y1))
        
        # Draw oblique line
        if self.show_oblique_line and hasattr(self.viewport, 'oblique_screen_coords'):
            p1, p2, h1, h2 = self.viewport.oblique_screen_coords
            
            # Draw main line
            pen = QPen(QColor(255, 165, 0), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(p1, p2)
            
            # Draw handle circles
            painter.setBrush(QColor(255, 165, 0, 180))
            painter.drawEllipse(h1, 6, 6)
            painter.drawEllipse(h2, 6, 6)

        
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
        
        self.data = self.manager.data
        self.header = self.manager.nifti_file.header
        self.pixdim = self.header['pixdim'][1:4]
        
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
        
        self.img_label = ImageLabel(self, orientation)
        self.side_bar = NavBar(self, self.current_slice, self.max_slices)
        
        self.viewport_layout.addWidget(self.side_bar)
        self.viewport_layout.addWidget(self.img_label)
        
        self.crosshair_pos = (None, None)
        self.roi_rect = (None, None, None, None)
        self.oblique_screen_coords = None
        
        self.slice_shape_before_transform = None
        self.slice_shape_after_transform = None
        self.scale_factor = (1.0, 1.0)
        
        self.display_slice(self.current_slice)

        # Anatomical position labels
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

        for lbl in self.labels.values():
            lbl.setStyleSheet("""
                color: yellow;
                font: bold 16px 'Arial';
                background: transparent;
                border: none;
            """)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.raise_()
        self._draw_anatomical_lables(None)

    def _draw_anatomical_lables(self, event):
        w, h = self.width(), self.height()
        margin = 10

        for lbl in self.labels.values():
            lbl.adjustSize()
    
        self.labels["top"].move(w // 2, margin)
        self.labels["bottom"].move(w // 2, h - self.labels["bottom"].height() - margin)
        self.labels["left"].move(margin + self.side_bar.width(), (h - self.labels["left"].height()) // 2)
        self.labels["right"].move(w - self.labels["right"].width() - margin, (h - self.labels["right"].height()) // 2)

    def get_aspect_ratio(self):
        if self.orientation == 'axial':
            return self.pixdim[0] / self.pixdim[1]
        elif self.orientation == 'sagittal':
            return self.pixdim[1] / self.pixdim[2]
        elif self.orientation == 'coronal':
            return self.pixdim[0] / self.pixdim[2]
        return 1.0

    def display_slice(self, slice_index):
        if slice_index < 0 or slice_index >= self.max_slices:
            return
        
        self.current_slice = slice_index
        
        if self.orientation == 'axial':
            slice_data = self.data[:, :, slice_index]
        elif self.orientation == 'sagittal':
            slice_data = self.data[slice_index, :, :]
        elif self.orientation == 'coronal':
            slice_data = self.data[:, slice_index, :]
        else:
            return
        
        self.slice_shape_before_transform = slice_data.shape
        
        slice_min, slice_max = np.min(slice_data), np.max(slice_data)
        if slice_max > slice_min:
            img = ((slice_data - slice_min) / (slice_max - slice_min) * 255).astype(np.uint8)
        else:
            img = np.zeros_like(slice_data, dtype=np.uint8)
        
        img = np.rot90(img, k=1)
        if self.orientation == "axial":
            img = np.flip(img)
        elif self.orientation == "coronal":
            img = np.fliplr(img)
        
        self.slice_shape_after_transform = img.shape
        img = np.ascontiguousarray(img)
        
        height, width = img.shape
        q_image = QImage(img.data, width, height, width, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        
        aspect_ratio = self.get_aspect_ratio()
        available_width = self.width() - 20
        available_height = self.height() - 20
        
        if available_width / available_height > aspect_ratio:
            target_height = available_height
            target_width = int(target_height * aspect_ratio)
        else:
            target_width = available_width
            target_height = int(target_width / aspect_ratio)
        
        if self.orientation in ["coronal", "sagittal"]:
            target_width = target_height
        
        scaled_pixmap = pixmap.scaled(
            target_width, target_height,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.scale_factor = (
            scaled_pixmap.width() / width,
            scaled_pixmap.height() / height
        )
        
        self.img_label.setPixmap(scaled_pixmap)

    def update_view(self, slice_index, cursor_voxel):
        self.display_slice(slice_index)
        self.side_bar.setValue(slice_index)
        
        self.crosshair_pos = self.voxel_to_image_coords(cursor_voxel)
        
        if hasattr(self.manager, 'roi_enabled') and self.manager.roi_enabled:
            self.roi_rect = self.get_roi_in_image_coords()
        else:
            self.roi_rect = (None, None, None, None)
        
        self.img_label.update()

    def update_oblique_line(self):
        """Update oblique line display on this viewport"""
        show_line = (self.manager.fourth_view_mode == "oblique" and 
                    self.manager.base_view_to4th == self.orientation)
        
        self.img_label.show_oblique_line = show_line
        
        if show_line:
            pixmap = self.img_label.pixmap()
            if pixmap:
                pixmap_rect = self.img_label.get_pixmap_rect()
                
                # Get normalized coordinates
                x1 = self.manager.oblique_line['x1']
                y1 = self.manager.oblique_line['y1']
                x2 = self.manager.oblique_line['x2']
                y2 = self.manager.oblique_line['y2']
                
                # Convert to screen coordinates
                screen_x1 = pixmap_rect.x() + x1 * pixmap.width()
                screen_y1 = pixmap_rect.y() + y1 * pixmap.height()
                screen_x2 = pixmap_rect.x() + x2 * pixmap.width()
                screen_y2 = pixmap_rect.y() + y2 * pixmap.height()
                
                p1 = QPointF(screen_x1, screen_y1)
                p2 = QPointF(screen_x2, screen_y2)
                
                # Handle positions (small circles at ends)
                h1 = QPointF(screen_x1, screen_y1)
                h2 = QPointF(screen_x2, screen_y2)
                
                self.oblique_screen_coords = (p1, p2, h1, h2)
        
        self.img_label.update()

    def voxel_to_image_coords(self, voxel):
        i, j, k = voxel
        
        if self.slice_shape_after_transform is None:
            return (None, None)
        
        pixmap = self.img_label.pixmap()
        if not pixmap:
            return (None, None)
        
        if self.orientation == 'axial':
            x_in_transformed = self.slice_shape_before_transform[0] - 1 - i
            y_in_transformed = j
        elif self.orientation == 'sagittal':
            x_in_transformed = j
            y_in_transformed = self.slice_shape_before_transform[1] - 1 - k
        elif self.orientation == 'coronal':
            x_in_transformed = self.slice_shape_before_transform[0] - 1 - i
            y_in_transformed = self.slice_shape_before_transform[1] - 1 - k
        else:
            return (None, None)
        
        x_display = x_in_transformed * self.scale_factor[0]
        y_display = y_in_transformed * self.scale_factor[1]
        
        return (x_display, y_display)

    def image_coords_to_voxel(self, img_x, img_y):
        if self.slice_shape_after_transform is None:
            return self.manager.cursor_voxel
        
        x_transformed = img_x / self.scale_factor[0]
        y_transformed = img_y / self.scale_factor[1]
        
        if self.orientation == 'axial':
            i = self.slice_shape_before_transform[0] - 1 - x_transformed
            j = y_transformed
            k = self.current_slice
        elif self.orientation == 'sagittal':
            i = self.current_slice
            j = x_transformed
            k = self.slice_shape_before_transform[1] - 1 - y_transformed
        elif self.orientation == 'coronal':
            i = self.slice_shape_before_transform[0] - 1 - x_transformed
            j = self.current_slice
            k = self.slice_shape_before_transform[1] - 1 - y_transformed
        else:
            return self.manager.cursor_voxel
        
        return np.array([i, j, k])

    def get_roi_in_image_coords(self):
        if not self.manager.roi_enabled:
            return (None, None, None, None)
        
        roi_start = self.manager.roi_start.copy()
        roi_end = self.manager.roi_end.copy()
        
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
        
        pos1 = self.voxel_to_image_coords(np.array(corners[0]))
        pos2 = self.voxel_to_image_coords(np.array(corners[1]))
        
        if None in pos1 or None in pos2:
            return (None, None, None, None)
        
        x1, y1 = min(pos1[0], pos2[0]), min(pos1[1], pos2[1])
        x2, y2 = max(pos1[0], pos2[0]), max(pos1[1], pos2[1])
        
        return (x1, y1, x2, y2)

    def move_roi(self, dx, dy):
        if not self.manager.roi_enabled:
            return
            
        scale_x = self.scale_factor[0]
        scale_y = self.scale_factor[1]
        
        voxel_dx = dx / scale_x
        voxel_dy = dy / scale_y
        
        roi_size = self.manager.roi_end - self.manager.roi_start
        
        if self.orientation == 'axial':
            delta_i = voxel_dx
            delta_j = voxel_dy
            new_start = self.manager.roi_start.copy()
            new_start[0] -= delta_i
            new_start[1] += delta_j
        elif self.orientation == 'sagittal':
            delta_j = voxel_dx
            delta_k = -voxel_dy
            new_start = self.manager.roi_start.copy()
            new_start[1] += delta_j
            new_start[2] += delta_k
        elif self.orientation == 'coronal':
            delta_i = voxel_dx
            delta_k = -voxel_dy
            new_start = self.manager.roi_start.copy()
            new_start[0] -= delta_i
            new_start[2] += delta_k
        
        shape = np.array(self.data.shape)
        new_start = np.clip(new_start, 0, shape - roi_size)
        new_end = new_start + roi_size
        
        self.manager.roi_start = new_start
        self.manager.roi_end = new_end
        self.manager._update_all_views()

    def resize_roi(self, dx, dy, edge):
        if not self.manager.roi_enabled:
            return
            
        scale_x = self.scale_factor[0]
        scale_y = self.scale_factor[1]
        
        voxel_dx = dx / scale_x
        voxel_dy = dy / scale_y
        
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
        
        for i in range(3):
            if self.manager.roi_start[i] > self.manager.roi_end[i]:
                self.manager.roi_start[i], self.manager.roi_end[i] = self.manager.roi_end[i], self.manager.roi_start[i]
        
        shape = self.data.shape
        self.manager.roi_start = np.clip(self.manager.roi_start, 0, shape)
        self.manager.roi_end = np.clip(self.manager.roi_end, 0, shape)
        self.manager._update_all_views()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'current_slice'):
            self.display_slice(self.current_slice)
            if hasattr(self.manager, 'cursor_voxel'):
                self.crosshair_pos = self.voxel_to_image_coords(self.manager.cursor_voxel)
                self.roi_rect = self.get_roi_in_image_coords()
                self.update_oblique_line()
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
        
        self.current_slice = new_slice
        self.side_bar.setValue(new_slice)
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
        
        def on_scroll_value_changed(value):
            self.viewport.current_slice = value
            new_cursor = self.viewport.manager.cursor_voxel.copy()
            if self.viewport.orientation == 'axial':
                new_cursor[2] = value
            elif self.viewport.orientation == 'sagittal':
                new_cursor[0] = value
            elif self.viewport.orientation == 'coronal':
                new_cursor[1] = value
            self.viewport.manager.cursor_voxel = new_cursor
            self.viewport.manager.cursor_world = self.viewport.manager._voxel_to_world(new_cursor)
            self.viewport.manager._update_all_views()
            
        self.scrollbar.valueChanged.connect(on_scroll_value_changed)
        layout.addWidget(self.scrollbar)

    def setValue(self, slice_idx):
        self.scrollbar.blockSignals(True)
        self.scrollbar.setValue(slice_idx)
        self.scrollbar.blockSignals(False)



class FourthView(QFrame):
    """
    FourthView: displays either a true oblique reformat plane or a scrollable outline slice.
    Expects manager to provide:
      - manager.img_ras : nib.Nifti1Image (required, canonical RAS)
      - manager.base_view_to4th : 'axial'|'sagittal'|'coronal'
      - manager.viewports : dict of viewports (optional). viewport.current_slice used if present
      - manager.oblique_line : dict {'x1','y1','x2','y2'} normalized to [0..1]
      - manager.fourth_view_mode : 'oblique'|'outline'|...
      - manager.segmentation_mask : optional (path to nifti, nib object or numpy array)
    Notes:
      - Assumes vol = img_ras.get_fdata() with shape (nx, ny, nz).
    """

    def __init__(self, manager):
        super().__init__(manager)
        self.manager = manager

        # UI
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("QFrame { background-color: black; border: 1px solid #444; }")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.img_label = QLabel(self)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("border: none; background-color: black;")
        self.img_label.setMouseTracking(True)
        self.img_label.installEventFilter(self)

        self.side_bar = QScrollBar(Qt.Vertical, self)
        self.side_bar.valueChanged.connect(self._on_scroll_changed)

        self.layout.addWidget(self.side_bar)
        self.layout.addWidget(self.img_label)

        # state
        nifti = getattr(self.manager, 'img_ras', None)
        if nifti is None:
            raise RuntimeError("manager.img_ras (Nifti1Image) required by FourthView")

        self.vol = nifti.get_fdata()
        self.affine = nifti.affine
        self.mask_data = None

        self.base_view = getattr(self.manager, 'base_view_to4th', 'axial')

        self.max_slices = self._get_max_slices()
        self.current_slice = int(self.max_slices // 2) if self.max_slices > 0 else 0
        self.side_bar.setRange(0, max(0, self.max_slices - 1))
        self.side_bar.setValue(self.current_slice)

        # cache & sync
        self._cached_oblique_key = None
        self._cached_slice = None
        self._last_pixmap_shape = None
        self._last_manager_sig = (None, None, None)  # (base_view, oblique fingerprint, viewport_slice)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(120)
        self._poll_timer.timeout.connect(self._poll_manager)
        self._poll_timer.start()

        # interaction
        self._last_cursor_state = None

        # settings
        self.out_max = 512  # clamp max resample dims (lower if too slow)
        self.out_min = 64
        self.slice_display_size = 256  # default square resample size (can be updated by resize)

        # initial draw
        self.update_view()

    # -------------------------
    # helpers
    # -------------------------
    def _get_max_slices(self):
        vol = self.vol
        base = getattr(self.manager, 'base_view_to4th', 'axial')
        if base == 'axial':
            return vol.shape[2]
        elif base == 'sagittal':
            return vol.shape[0]
        elif base == 'coronal':
            return vol.shape[1]
        return max(vol.shape)

    def _on_scroll_changed(self, value):
        self.current_slice = int(value)
        self.side_bar.setValue(self.current_slice)
        self.update_view()

    def wheelEvent(self, event):
        if not getattr(self.manager, "outline_action", None) or not self.manager.outline_action.isChecked():
            return

        delta = event.angleDelta().y() // 120
        if delta == 0:
            return
        new_slice = int(np.clip(self.current_slice - delta, 0, max(0, self.max_slices - 1)))
        if new_slice != self.current_slice:
            self.current_slice = new_slice
            self.side_bar.setValue(new_slice)
            self.update_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # clear cache so we recompute with the new output size
        self._cached_oblique_key = None
        self.update_view()

    def _poll_manager(self):
        """Detect external changes to manager (base view, oblique line, or viewport slice)"""
        base = getattr(self.manager, 'base_view_to4th', None)
        ol = getattr(self.manager, 'oblique_line', None)
        ol_fp = None
        if isinstance(ol, dict):
            ol_fp = (round(float(ol.get('x1', 0)), 4), round(float(ol.get('y1', 0)), 4),
                     round(float(ol.get('x2', 0)), 4), round(float(ol.get('y2', 0)), 4),
                     ol.get('base', None))
        viewport = getattr(self.manager, 'viewports', {}).get(base, None)
        vp_slice = getattr(viewport, 'current_slice', None) if viewport is not None else None
        sig = (base, ol_fp, vp_slice)
        if sig != self._last_manager_sig:
            prev_base = self._last_manager_sig[0]
            if prev_base is not None and base != prev_base:
                # base changed -> hide/clear any stale oblique state
                self._cached_oblique_key = None
                self._cached_slice = None
            self._last_manager_sig = sig
            # refresh view
            self.update_view()

    # -------------------------
    # main update
    # -------------------------
    def update_view(self):
        # hide scrollbar when not in outline mode
        if hasattr(self.manager, "outline_action") and not self.manager.outline_action.isChecked():
            self.side_bar.hide()
        # else:                         # Not needed for our app now
        #     self.side_bar.show()

        if not getattr(self.manager, "oblique_action", None) and not getattr(self.manager, "outline_action", None):
            self.img_label.clear()
            return

        nifti = getattr(self.manager, 'img_ras', None)
        if nifti is not None:
            self.vol = nifti.get_fdata()
            self.affine = nifti.affine

        mode = getattr(self.manager, 'fourth_view_mode', 'oblique')
        self.base_view = getattr(self.manager, 'base_view_to4th', self.base_view)

        if mode == 'oblique' and getattr(self.manager, "oblique_action", None) and self.manager.oblique_action.isChecked():
            ol = getattr(self.manager, 'oblique_line', None)
            if not ol:
                self.img_label.clear()
                return
            # if oblique_line tracks 'base' and doesn't match current base -> hide
            if isinstance(ol, dict) and 'base' in ol and ol['base'] != self.base_view:
                self.img_label.clear()
                return
            self._display_oblique()
        elif mode == 'outline' and getattr(self.manager, "outline_action", None) and self.manager.outline_action.isChecked():
            self.max_slices = self._get_max_slices()
            self.side_bar.setRange(0, max(0, self.max_slices - 1))
            self.current_slice = int(self.max_slices // 2) if self.max_slices > 0 else 0
            self.side_bar.setRange(0, max(0, self.max_slices - 1))
            self.side_bar.setValue(self.current_slice)
            self._display_outline()
        else:
            self.img_label.clear()

    # -------------------------
    # oblique reconstruction
    # -------------------------
    def _map_norm_to_voxel(self, x_norm, y_norm, base_view, slice_idx):
        """
        Map a normalized (0..1) coordinate on the base 2D viewport to voxel coordinates (x,y,z).
        IMPORTANT: Many view coordinates have origin at top-left (y down). We invert y to map correctly
        to voxel coordinates (so superior/inferior are correct).
        """
        s = self.vol.shape  # (nx, ny, nz)
        # invert y_norm (screen coordinates: y=0 top -> voxel y should be top -> invert)
        y_norm_inv = 1.0 - y_norm

        if base_view == 'axial':
            # x across vol.shape[0], y across vol.shape[1], z is slice index
            x = x_norm * (s[0] - 1)
            y = y_norm_inv * (s[1] - 1)
            z = float(slice_idx)
            return np.array([x, y, z], dtype=np.float64)

        elif base_view == 'sagittal':
            # sagittal view usually shows (z vs y) with x = slice index
            x = float(slice_idx)
            y = x_norm * (s[1] - 1)
            z = y_norm_inv * (s[2] - 1)
            return np.array([x, y, z], dtype=np.float64)

        elif base_view == 'coronal':
            # coronal view usually shows (x vs z) with y = slice index
            x = x_norm * (s[0] - 1)
            y = float(slice_idx)
            z = y_norm_inv * (s[2] - 1)
            return np.array([x, y, z], dtype=np.float64)

        else:
            return np.array([0.0, 0.0, 0.0], dtype=np.float64)

    def _display_oblique(self):
        vol = self.vol
        if vol is None:
            self.img_label.clear()
            return

        base = self.base_view
        viewport = getattr(self.manager, 'viewports', {}).get(base, None)
        slice_idx = getattr(viewport, 'current_slice', None) if viewport is not None else self.current_slice
        if slice_idx is None:
            slice_idx = self.current_slice

        ol = getattr(self.manager, 'oblique_line', None)
        if not isinstance(ol, dict):
            self.img_label.clear()
            return
        x1, y1 = float(ol['x1']), float(ol['y1'])
        x2, y2 = float(ol['x2']), float(ol['y2'])

        # map to voxel coords in that base slice (now using inverted y)
        p1 = self._map_norm_to_voxel(x1, y1, base, slice_idx)
        p2 = self._map_norm_to_voxel(x2, y2, base, slice_idx)

        # direction along the drawn line (in base plane)
        v = p2 - p1
        v_norm = np.linalg.norm(v)
        if v_norm < 1e-6:
            self.img_label.clear()
            return
        v_dir = v / v_norm

        # base plane normal
        if base == 'axial':
            base_n = np.array([0.0, 0.0, 1.0])
        elif base == 'sagittal':
            base_n = np.array([1.0, 0.0, 0.0])
        else:  # coronal
            base_n = np.array([0.0, 1.0, 0.0])

        # plane normal and in-plane perpendicular
        plane_n = np.cross(v_dir, base_n)
        plane_n_norm = np.linalg.norm(plane_n)
        if plane_n_norm < 1e-6:
            plane_n = np.cross(v_dir, np.array([1.0, 0.0, 0.0]))
            plane_n_norm = np.linalg.norm(plane_n)
            if plane_n_norm < 1e-6:
                plane_n = np.cross(v_dir, np.array([0.0, 1.0, 0.0]))
                plane_n_norm = np.linalg.norm(plane_n)
        plane_n = plane_n / (plane_n_norm + 1e-12)

        s_dir = np.cross(plane_n, v_dir)
        s_dir = s_dir / (np.linalg.norm(s_dir) + 1e-12)

        origin = 0.5 * (p1 + p2)  # center the line

        # determine output sampling size (based on display size and clamp)
        avail_w = max(self.out_min, min(self.out_max, int(self.width() - 20)))
        avail_h = max(self.out_min, min(self.out_max, int(self.height() - 20)))
        out_w = min(avail_w, avail_h)
        out_h = int(out_w)  # make square for simplicity

        # sampling extents in voxels
        half_v = max(v_norm * 0.6, max(self.vol.shape) * 0.12)
        half_s = max(max(self.vol.shape) * 0.12, v_norm * 0.25)

        uu = np.linspace(-half_v, half_v, out_w)   # along line
        vv = np.linspace(-half_s, half_s, out_h)   # perpendicular in-plane
        UU, VV = np.meshgrid(uu, vv, indexing='xy')

        plane_pts = origin[:, None, None] + (v_dir[:, None, None] * UU[None, :, :]) + (s_dir[:, None, None] * VV[None, :, :])
        coords = np.vstack((plane_pts[0].ravel(), plane_pts[1].ravel(), plane_pts[2].ravel()))

        # clamp coords
        for ax in range(3):
            coords[ax] = np.clip(coords[ax], 0, vol.shape[ax] - 1)

        key = (base, int(slice_idx), round(coords[0][0], 3), round(coords[1][0], 3), out_w, out_h)

        if key == self._cached_oblique_key and self._cached_slice is not None:
            slice_data = self._cached_slice
        else:
            # use constant fill with volume minimum to avoid border stretching noise
            sampled = map_coordinates(vol, coords, order=1, mode='constant', cval=np.min(vol))
            slice_data = sampled.reshape((out_h, out_w))
            self._cached_oblique_key = key
            self._cached_slice = slice_data

        # normalize and display (no flip here — mapping fixed earlier)
        img = self._normalize_img(slice_data)
        self._set_pixmap(img)

    # -------------------------
    # outline mode
    # -------------------------
    def _ensure_mask_loaded(self):
        if self.mask_data is not None:
            return True
        mask_obj = getattr(self.manager, 'segmentation_mask', None)
        if mask_obj is None:
            return False
        if isinstance(mask_obj, np.ndarray):
            self.mask_data = mask_obj
            return True
        if isinstance(mask_obj, str):
            try:
                nif = nib.load(mask_obj)
                nif = nib.as_closest_canonical(nif)
                self.mask_data = nif.get_fdata()
                return True
            except Exception:
                return False
        try:
            self.mask_data = mask_obj.get_fdata()
            return True
        except Exception:
            return False

    def _display_outline(self):
        if not self._ensure_mask_loaded():
            self.img_label.clear()
            return
        mask = self.mask_data
        base = self.base_view
        viewport = getattr(self.manager, 'viewports', {}).get(base, None)
        slice_idx = getattr(viewport, 'current_slice', None) if viewport is not None else self.current_slice
        if slice_idx is None:
            slice_idx = self.current_slice

        # slice selection per orientation
        if base == 'axial':
            if int(slice_idx) < 0 or int(slice_idx) >= mask.shape[2]:
                self.img_label.clear(); return
            mask_slice = mask[:, :, int(slice_idx)]
            mask_slice = np.rot90(mask_slice, k=-1)
        elif base == 'sagittal':
            if int(slice_idx) < 0 or int(slice_idx) >= mask.shape[0]:
                self.img_label.clear(); return
            mask_slice = mask[int(slice_idx), :, :]
            mask_slice = np.rot90(mask_slice, k=1)
        else:  # coronal
            if int(slice_idx) < 0 or int(slice_idx) >= mask.shape[1]:
                self.img_label.clear(); return
            mask_slice = mask[:, int(slice_idx), :]
            mask_slice = np.fliplr(np.rot90(mask_slice, k=1))

        mask_bin = (np.nan_to_num(mask_slice) > 0).astype(np.uint8) * 255
        mask_bin = np.ascontiguousarray(mask_bin)
        contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        outline_img = np.zeros_like(mask_bin, dtype=np.uint8)
        if contours:
            cv2.drawContours(outline_img, contours, -1, color=255, thickness=1)
        img = self._normalize_img(outline_img)
        self._set_pixmap(img)

    # -------------------------
    # image conversions
    # -------------------------
    def _normalize_img(self, arr):
        a = np.nan_to_num(arr.astype(np.float64))
        mn, mx = float(np.min(a)), float(np.max(a))
        if mx > mn:
            out = ((a - mn) / (mx - mn) * 255.0).astype(np.uint8)
        else:
            out = np.zeros_like(a, dtype=np.uint8)
        return out

    def _set_pixmap(self, img):
        img = np.ascontiguousarray(img)
        h, w = img.shape[:2]
        bytes_per_line = int(img.strides[0])
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_Grayscale8).copy()
        pixmap = QPixmap.fromImage(qimg)
        if getattr(self.manager, "outline_action", None) and self.manager.outline_action.isChecked():
            avail_w = max(32, int(self.width() - self.side_bar.width() - 20))
        else:
            avail_w = max(32, int(self.width() - 20))

        avail_h = max(32, int(self.height() - 20))
        scaled = pixmap.scaled(avail_w, avail_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(scaled)
        self._last_pixmap_shape = (pixmap.width(), pixmap.height())

        