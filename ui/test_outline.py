import nibabel as nib
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import binary_erosion, binary_dilation


# =====================================
# 1️⃣ Load Segmentation Mask (NIfTI)
# =====================================
# Replace with your mask file path
mask_path = r"E:\Ziad\Anatomy tasks\task1-image segmentaton\kidney\Total Segmentator\kidney_right.nii.gz"

print(f"Loading mask from: {mask_path}")
mask_nii = nib.load(mask_path)
mask_data = mask_nii.get_fdata()

print("Mask shape:", mask_data.shape)
print("Unique values:", np.unique(mask_data)[:10])

# --------------------------
# Choose label(s) to display
# --------------------------
# Example: 1 = heart, 2 = liver, etc.
mask_data = mask_data == 1    # adjust label if needed

nonzero_voxels = np.count_nonzero(mask_data)
print("Number of nonzero voxels:", nonzero_voxels)
if nonzero_voxels == 0:
    raise ValueError("❌ Mask seems empty. Try changing the label (e.g. mask_data == 2).")


# =====================================
# 2️⃣ Find valid slice indices
# =====================================
z_indices = np.where(mask_data.sum(axis=(0, 1)) > 0)[0]
if len(z_indices) == 0:
    raise ValueError("❌ No slices contain segmentation data.")
print(f"Found {len(z_indices)} slices with mask data.")
start_slice = z_indices[len(z_indices)//2]  # start from middle segmented slice


# =====================================
# 3️⃣ Slice Viewer Class
# =====================================
class SliceViewer:
    def __init__(self, mask, valid_z):
        self.mask = mask
        self.valid_z = valid_z
        self.z_idx = valid_z[len(valid_z)//2]
        self.fig, self.ax = plt.subplots()
        self.im = None

        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.show_slice()
        plt.show()

    def compute_outline(self, slice_mask):
        # combine dilation and erosion for more visible outline
        dil = binary_dilation(slice_mask)
        ero = binary_erosion(slice_mask)
        return dil ^ ero

    def show_slice(self):
        slice_mask = self.mask[:, :, self.z_idx]
        outline = self.compute_outline(slice_mask)

        img = np.zeros_like(slice_mask, dtype=float)
        img[outline] = 1.0

        if self.im is None:
            self.im = self.ax.imshow(img, cmap='gray', interpolation='nearest')
        else:
            self.im.set_data(img)

        self.ax.set_title(f"Slice Z = {self.z_idx} ({self.valid_z.index(self.z_idx)+1}/{len(self.valid_z)})")
        self.ax.axis('off')
        self.fig.canvas.draw_idle()

    def on_scroll(self, event):
        i = self.valid_z.index(self.z_idx)
        if event.button == 'up':
            i = (i + 1) % len(self.valid_z)
        elif event.button == 'down':
            i = (i - 1) % len(self.valid_z)
        self.z_idx = self.valid_z[i]
        self.show_slice()


# =====================================
# 4️⃣ Run Viewer
# =====================================
print("🟢 Starting slice viewer — scroll mouse wheel to move through slices.")
SliceViewer(mask_data, valid_z=list(z_indices))

