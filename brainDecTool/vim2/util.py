# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import glob
import numpy as np
import nibabel as nib
import matplotlib.pylab as plt
import matplotlib.image as mpimg

from brainDecTool.math import corr2_coef

def idx2coord(vec_idx):
    """Convert row index in response data matrix into 3D coordinate in
    (original) ROI volume.
    """
    data_size = (18, 64, 64)
    coord_z = vec_idx % data_size[2]
    coord_x = vec_idx / (data_size[1]*data_size[2])
    coord_y = (vec_idx % (data_size[1]*data_size[2])) / data_size[2]
    return (coord_x, coord_y, coord_z)

def coord2idx(coord):
    """Convert a 3D coordinate from nifti file into row index in response
    data matrix.
    Input must be a tuple.
    """
    ncoord = (coord[2], coord[0], 63-coord[1])
    return ncoord[2]+ncoord[0]*64*64+ncoord[1]*64

def node2feature(node_idx, data_shape):
    """Convert node index from CNN activation vector into 3 features including
    index of channel, row and column position of the filter.
    Return a tuple of (channel index, row index, column index).
    """
    #data_size = {'conv1': [96, 55, 55],
    #             'conv2': [256, 27, 27],
    #             'conv3': [384, 13, 13],
    #             'conv4': [384, 13, 13],
    #             'cpnv5': [256, 13, 13],
    #             'pool5': [256, 6, 6]}
    #s = data_size[layer_name]
    s = data_shape
    col_idx = node_idx % s[2]
    channel_idx = node_idx / (s[1]*s[2])
    row_idx = (node_idx % (s[1]*s[2])) / s[2]
    return (channel_idx, row_idx, col_idx)

def save2nifti(data, filename):
    """Save 3D data as nifti file.
    Original data shape is (18, 64, 64), and the resulting data shape is
    (64, 64, 18) which orientation is SRP."""
    # roll axis
    ndata = np.rollaxis(data, 0, 3)
    ndata = ndata[:, ::-1, :]
    # generate affine matrix
    aff = np.zeros((4, 4))
    aff[0, 1] = 2
    aff[1, 2] = -2.5
    aff[2, 0] = 2
    aff[3, 3] = 1
    img = nib.Nifti1Image(ndata, aff)
    nib.save(img, filename)

def mask2nifti(data, filename):
    """Save 3D mask derived from pycortex as nifti file.
    Original data shape is (18, 64, 64), and the resulting data shape is
    (64, 64, 18) which orientation is SRP."""
    # roll axis
    data = data.astype('<f8')
    ndata = np.rollaxis(data, 0, 3)
    ndata = np.rollaxis(ndata, 0, 2)
    ndata = ndata[:, ::-1, :]
    # generate affine matrix
    aff = np.zeros((4, 4))
    aff[0, 1] = 2
    aff[1, 2] = -2.5
    aff[2, 0] = 2
    aff[3, 3] = 1
    img = nib.Nifti1Image(ndata, aff)
    nib.save(img, filename)

def plot_prf(prf_file):
    """Plot pRF."""
    prf_data = np.load(prf_file)
    vxl = prf_data[..., 0]
    # figure config

    for f in range(96):
        fig, axs = plt.subplots(5, 8)
        for t in range(40):
            tmp = vxl[:, t].reshape(96, 55, 55)
            tmp = tmp[f, :]
            im = axs[t/8][t%8].imshow(tmp, interpolation='nearest',
                                      cmap=plt.cm.ocean,
                                      vmin=-0.2, vmax=0.3)
        fig.colorbar(im)
        #plt.show()
        fig.savefig('%s.png'%(f))

def channel_sim(feat_file):
    """Compute similarity between each pair of channels."""
    feat = np.load(feat_file)
    print feat.shape
    feat = feat.reshape(96, 55, 55, 540)
    simmtx = np.zeros((feat.shape[0], feat.shape[0]))
    for i in range(feat.shape[0]):
        for j in range(i+1, feat.shape[0]):
            print '%s - %s' %(i, j)
            x = feat[i, :].reshape(-1, feat.shape[3])
            y = feat[j, :].reshape(-1, feat.shape[3])
            tmp = corr2_coef(x, y)
            tmp = tmp.diagonal()
            simmtx[i, j] = tmp.mean()
    np.save('sim_mtx.npy', simmtx)
    im = plt.imshow(simmtx, interpolation='nearest', cmap=plt.cm.ocean)
    plt.colorbar(im)
    plt.show()

def data_swap(nifti_file):
    """Convert nifti data into original data shape."""
    data = nib.load(nifti_file).get_data()
    ndata = data[:, ::-1, :]
    ndata = np.rollaxis(ndata, 0, 3)
    ndata = np.rollaxis(ndata, 0, 3)
    return ndata

def plot_cca_fweights(data, out_dir, prefix_name, abs_flag=True):
    """Plot features weights derived from CCA."""
    if len(data.shape)==4:
        n_components = data.shape[3]
    elif len(data.shape)==3:
        n_components = 1
    n_channels = data.shape[0]

    if abs_flag:
        maxv = np.abs(data).max()
        minv = 0
    else:
        maxv = data.max()
        minv = data.min()
    for f in range(n_components):
        fig, axs = plt.subplots(8, 12)
        for c in range(n_channels):
            if len(data.shape)==3:
                if abs_flag:
                    tmp = np.abs(data[c, ...])
                else:
                    tmp = data[c, ...]
            else:
                if abs_flag:
                    tmp = np.abs(data[c, ..., f])
                else:
                    tmp = data[c, ..., f]
            im = axs[c/12][c%12].imshow(tmp, interpolation='nearest',
                                        vmin=minv, vmax=maxv)
            axs[c/12][c%12].get_xaxis().set_visible(False)
            axs[c/12][c%12].get_yaxis().set_visible(False)
        fig.subplots_adjust(right=0.85)
        cbar_ax = fig.add_axes([0.88, 0.2, 0.03, 0.6])
        fig.colorbar(im, cax=cbar_ax)
        fig.savefig(os.path.join(out_dir, prefix_name+'_%s.png'%(f+1)))

def save_cca_volweights(fmri_weights, mask_file, out_dir,
                        prefix_name='cca_component'):
    """Save fmri weights derived from CCA as nifti files."""
    n_components = fmri_weights.shape[1]
    mask = data_swap(mask_file)
    vxl_idx = np.nonzero(mask.flatten()==1)[0]
    for i in range(n_components):
        tmp = np.zeros_like(mask.flatten(), dtype=np.float64)
        tmp[vxl_idx] = fmri_weights[:, i]
        tmp = tmp.reshape(mask.shape)
        save2nifti(tmp, os.path.join(out_dir, prefix_name+'_%s.nii.gz'%(i+1)))

def display_video(dataset):
    """Display 3D video."""
    plt.ion()
    for i in range(dataset.shape[2]):
        plt.imshow(dataset[:, i])
        plt.pause(0.05)

def plot_kernerls(in_dir, basename, filename):
    """Plot several kernel images in one screen."""
    file_num = len(glob.glob(os.path.join(in_dir, basename+'*')))
    fig, axs = plt.subplots(8, 12)
    for n in range(file_num):
        f = os.path.join(in_dir, basename+str(n)+'.png')
        img = mpimg.imread(f)
        im = axs[n/12][n%12].imshow(img)
        axs[n/12][n%12].get_xaxis().set_visible(False)
        axs[n/12][n%12].get_yaxis().set_visible(False)
    fig.savefig(os.path.join(in_dir, filename))

def fweights_bar(feat_weights):
    """Bar plots for feature weights derived from CCA.
    For each feature/2D feature map, top 20% `abs` weights are averaged
    for evaluation.
    """
    cc_num = feat_weights.shape[3]
    channel_num = feat_weights.shape[0]
    fig, axs = plt.subplots(cc_num, 1)
    for i in range(cc_num):
        tmp = feat_weights[..., i]
        ws = []
        for j in range(channel_num):
            ctmp = np.abs(tmp[j, ...]).flatten()
            ctmp.sort()
            m = ctmp[-1*int(ctmp.shape[0]*0.2):].mean()
            ws.append(m)
        ind = np.arange(channel_num)
        axs[i].bar(ind, ws, 0.35)
    plt.show()

def roi2nifti(fmri_table, filename, mode='full'):
    """Save ROI as a nifti file.
    `mode`: 'full' for whole ROIs mask creation.
            'small' for mask creation for alignment.
    """
    if mode=='full':
        roi_label = {'v1lh': 1, 'v1rh': 2, 'v2lh': 3, 'v2rh': 4,
                     'v3lh': 5, 'v3rh': 6, 'v3alh': 7, 'v3arh': 8,
                     'v3blh': 9, 'v3brh': 10, 'v4lh': 11, 'v4rh': 12,
                     'latocclh': 13, 'latoccrh': 14, 'VOlh': 15, 'VOrh': 16,
                    'STSlh': 17, 'STSrh': 18, 'RSClh': 19, 'RSCrh': 20,
                    'PPAlh': 21, 'PPArh': 22, 'OBJlh': 23, 'OBJrh': 24,
                    'MTlh': 25, 'MTrh': 26, 'MTplh': 27, 'MTprh': 28,
                    'IPlh': 29, 'IPrh': 30, 'FFAlh': 31, 'FFArh': 32,
                    'EBAlh': 33, 'EBArh': 34, 'OFAlh': 35, 'OFArh': 36,
                    'v7alh': 37, 'v7arh': 38, 'v7blh': 39, 'v7brh': 40,
                    'v7clh': 41, 'v7crh': 42, 'v7lh': 43, 'v7rh': 44,
                    'IPS1lh': 45, 'IPS1rh': 46, 'IPS2lh': 47, 'IPS2rh': 48,
                    'IPS3lh': 49, 'IPS3rh': 50, 'IPS4lh': 51, 'IPS4rh': 52,
                    'MSTlh': 53, 'MSTrh': 54, 'TOSlh': 55, 'TOSrh': 56}
    else:
        roi_label = {'v1lh': 1, 'v1rh': 2, 'v2lh': 3, 'v2rh': 4,
                     'v3lh': 5, 'v3rh': 6, 'v3alh': 7, 'v3arh': 8,
                     'v3blh': 9, 'v3brh': 10, 'v4lh': 11, 'v4rh': 12,
                    'MTlh': 13, 'MTrh': 14, 'MTplh': 15, 'MTprh': 16}

    roi_list = fmri_table.list_nodes('/roi')
    roi_shape = roi_list[0].shape
    roi_mask = np.zeros(roi_shape)
    roi_list = [r.name for r in roi_list if r.name in roi_label]
    for r in roi_list:
        roi_mask += fmri_table.get_node('/roi/%s'%(r))[:] * roi_label[r]
    save2nifti(roi_mask, filename)

def get_roi_mask(fmri_table, nifti=False):
    """Save ROIs as a mask."""
    roi_list = fmri_table.list_nodes('/roi')
    roi_shape = roi_list[0].shape
    mask = np.zeros(roi_shape)
    for r in roi_list:
        mask += fmri_table.get_node('/roi/%s'%(r.name))[:]
    if nifti:
        save2nifti(mask, 'all_roi_mask.nii.gz')
    else:
        return mask.flatten()

def gen_mean_vol(fmri_table, dataset, filename):
    """Make a mean response map as a reference volume."""
    data = fmri_table.get_node('/'+dataset)[:]
    # replace nan to zero
    data = np.nan_to_num(data)
    mean_data = np.mean(data, axis=1)
    vol = np.zeros((18, 64, 64))
    
    for i in range(data.shape[0]):
        c = vutil.idx2coord(i)
        vol[c[0], c[1], c[2]] = mean_data[i]
    
    save2nifti(vol, filename)

