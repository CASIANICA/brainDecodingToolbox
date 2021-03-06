# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import numpy as np
from scipy import ndimage
from scipy.misc import imsave
from sklearn.cross_decomposition import PLSRegression
from sklearn.externals import joblib

from braincode.util import configParser
from braincode.math import corr2_coef
from braincode.math import get_pls_components, pls_regression_predict
from braincode.pipeline import retinotopy
from braincode.prf import util as vutil
from braincode.vim2 import dataio


def check_path(dir_path):
    """Check whether the directory does exist, if not, create it."""
    if not os.path.exists(dir_path):
        os.mkdir(dir_path, 0755)

def retinotopic_mapping(corr_file, data_dir, vxl_idx=None, figout=False):
    """Make the retinotopic mapping using activation map from CNN."""
    if figout:
        fig_dir = os.path.join(data_dir, 'fig')
        check_path(fig_dir)
    # load the cross-correlation matrix from file
    corr_mtx = np.load(corr_file, mmap_mode='r')
    # set voxel index
    if not isinstance(vxl_idx, np.ndarray):
        vxl_idx = np.arange(corr_mtx.shape[0])
    elif len(vxl_idx) != corr_mtx.shape[0]:
        print 'mismatch on voxel number!'
        return
    else:
        print 'voxel index loaded.'
    img_size = 55.0
    pos_mtx = np.zeros((73728, 2))
    pos_mtx[:] = np.nan
    for i in range(len(vxl_idx)):
        print 'Iter %s of %s' %(i+1, len(vxl_idx)),
        tmp = corr_mtx[i, :]
        tmp = np.nan_to_num(np.array(tmp))
        # significant threshold for one-tail test
        tmp[tmp <= 0.019257] = 0
        if np.sum(tmp):
            mmtx = tmp.reshape(55, 55)
            #tmp = tmp.reshape(96, 27, 27)
            #mmtx = np.max(tmp, axis=0)
            print mmtx.min(), mmtx.max()
            if figout:
                fig_file = os.path.join(fig_dir, 'v'+str(vxl_idx[i])+'.png')
                imsave(fig_file, mmtx)
            # get indices of n maximum values
            max_n = 20
            row_idx, col_idx = np.unravel_index(
                                        np.argsort(mmtx.ravel())[-1*max_n:],
                                        mmtx.shape)
            nmtx = np.zeros(mmtx.shape)
            nmtx[row_idx, col_idx] = mmtx[row_idx, col_idx]
            # center of mass
            x, y = ndimage.measurements.center_of_mass(nmtx)
            pos_mtx[vxl_idx[i], :] = [x, y]
        else:
            print ' '
    #receptive_field_file = os.path.join(data_dir, 'receptive_field_pos.npy')
    #np.save(receptive_field_file, pos_mtx)
    #pos_mtx = np.load(receptive_field_file)
    # generate retinotopic mapping
    base_name = 'train_max' + str(max_n)
    prf2visual_angle(pos_mtx, img_size, data_dir, base_name)

def prf2visual_angle(prf_mtx, img_size, out_dir, base_name):
    """Generate retinotopic mapping based on voxels' pRF parameters.
    `prf_mtx` is a #voxel x pRF-features matrix, pRF features can be 2 columns
    (row, col) of image or 3 columns which adding a third pRF size parameters.

    """
    feature_size = prf_mtx.shape[1]
    pos_mtx = prf_mtx[:, :2]
    # eccentricity
    ecc = retinotopy.coord2ecc(pos_mtx, img_size, 20)
    vol = ecc.reshape(18, 64, 64)
    vutil.save2nifti(vol, os.path.join(out_dir, base_name+'_ecc.nii.gz'))
    # angle
    angle = retinotopy.coord2angle(pos_mtx, img_size)
    vol = angle.reshape(18, 64, 64)
    vutil.save2nifti(vol, os.path.join(out_dir, base_name+'_angle.nii.gz'))
    # pRF size
    if feature_size > 2:
        size_angle = retinotopy.get_prf_size(prf_mtx, 55, 20)
        vol = size_angle.reshape(18, 64, 64)
        vutil.save2nifti(vol, os.path.join(out_dir, base_name+'_size.nii.gz'))

def pls_y_pred_x(plsca, Y):
    """Predict X based on Y using a trained PLS CCA model `plsca`.
    """
    coef_ = np.dot(plsca.y_rotations_, plsca.x_loadings_.T)
    coef_ = (1./plsca.y_std_.reshape((plsca.y_weights_.shape[0], 1)) * coef_ *
            plsca.x_std_)
    # Normalize
    Yk = Y - plsca.y_mean_
    Yk /= plsca.y_std_
    Xpred = np.dot(Y, coef_)
    return Xpred + plsca.x_mean_

def plscorr_eval(train_fmri_ts, train_feat_ts, val_fmri_ts, val_feat_ts,
                 out_dir, mask_file):
    """Compute PLS correlation between brain activity and CNN activation."""
    train_feat_ts = train_feat_ts.reshape(-1, train_feat_ts.shape[3]).T
    val_feat_ts = val_feat_ts.reshape(-1, val_feat_ts.shape[3]).T
    train_fmri_ts = train_fmri_ts.T
    val_fmri_ts = val_fmri_ts.T

    # Iteration loop for different component number
    #for n in range(5, 19):
    #    print '--- Components number %s ---' %(n)
    #    plsca = PLSCanonical(n_components=n)
    #    plsca.fit(train_feat_ts, train_fmri_ts)
    #    pred_feat_c, pred_fmri_c = plsca.transform(val_feat_ts, val_fmri_ts)
    #    pred_fmri_ts = plsca.predict(val_feat_ts) 
    #    # calculate correlation coefficient between truth and prediction
    #    r = corr2_coef(val_fmri_ts.T, pred_fmri_ts.T, mode='pair')
    #    # get top 20% corrcoef for model evaluation
    #    vsample = int(np.rint(0.2*len(r)))
    #    print 'Sample size for evaluation : %s' % (vsample)
    #    r.sort()
    #    meanr = np.mean(r[-1*vsample:])
    #    print 'Mean prediction corrcoef : %s' %(meanr)
    
    # model generation based on optimized CC number
    cc_num = 10
    plsca = PLSCanonical(n_components=cc_num)
    plsca.fit(train_feat_ts, train_fmri_ts)
    from sklearn.externals import joblib
    joblib.dump(plsca, os.path.join(out_dir, 'plsca_model.pkl'))
    plsca = joblib.load(os.path.join(out_dir, 'plsca_model.pkl'))

    # calculate correlation coefficient between truth and prediction
    pred_fmri_ts = plsca.predict(val_feat_ts)
    fmri_pred_r = corr2_coef(val_fmri_ts.T, pred_fmri_ts.T, mode='pair')
    mask = vutil.data_swap(mask_file)
    vxl_idx = np.nonzero(mask.flatten()==1)[0]
    tmp = np.zeros_like(mask.flatten(), dtype=np.float64)
    tmp[vxl_idx] = fmri_pred_r
    tmp = tmp.reshape(mask.shape)
    vutil.save2nifti(tmp, os.path.join(out_dir, 'pred_fmri_r.nii.gz'))
    pred_feat_ts = pls_y_pred_x(plsca, val_fmri_ts)
    pred_feat_ts = pred_feat_ts.T.reshape(96, 14, 14, 540)
    np.save(os.path.join(out_dir, 'pred_feat.npy'), pred_feat_ts)

    # get PLS-CCA weights
    feat_cc, fmri_cc = plsca.transform(train_feat_ts, train_fmri_ts)
    np.save(os.path.join(out_dir, 'feat_cc.npy'), feat_cc)
    np.save(os.path.join(out_dir, 'fmri_cc.npy'), fmri_cc)
    feat_weight = plsca.x_weights_.reshape(96, 14, 14, cc_num)
    #feat_weight = plsca.x_weights_.reshape(96, 11, 11, cc_num)
    fmri_weight = plsca.y_weights_
    np.save(os.path.join(out_dir, 'feat_weights.npy'), feat_weight)
    np.save(os.path.join(out_dir, 'fmri_weights.npy'), fmri_weight)
    fmri_orig_ccs = get_pls_components(plsca.y_scores_, plsca.y_loadings_)
    np.save(os.path.join(out_dir, 'fmri_orig_ccs.npy'), fmri_orig_ccs)

def inter_subj_cc_sim(subj1_id, subj2_id, subj_dir):
    """Compute inter-subjects CCs similarity."""
    subj1_dir = os.path.join(subj_dir, 'vS%s'%(subj1_id))
    subj2_dir = os.path.join(subj_dir, 'vS%s'%(subj2_id))
    #-- inter-channel similarity
    feat_weights_file1 = os.path.join(subj1_dir, 'plscca',
                                      'layer1', 'feat_weights.npy')
    feat_weights_file2 = os.path.join(subj2_dir, 'plscca',
                                      'layer1', 'feat_weights.npy')
    feat_cc_corr1 = np.load(feat_cc_corr_file1).reshape(96, 121, 10)
    feat_cc_corr2 = np.load(feat_cc_corr_file2).reshape(96, 121, 10)
    sim_mtx = np.zeros((960, 960))
    for i in  range(10):
        data1 = feat_cc_corr1[..., i]
        for j in range(10):
            data2 = feat_cc_corr2[..., j]
            tmp = corr2_coef(data1, data2)
            sim_mtx[i*96:(i+1)*96, j*96:(j+1)*96] = np.abs(tmp)
    np.save('feat_cc_weights_sim_subj_%s_%s.npy'%(subj1_id, subj2_id), sim_mtx)
    #-- inter-CC similarity
    #feat_cc_corr_file1 = os.path.join(subj1_dir, 'plscca',
    #                                  'layer1', 'feat_cc_corr.npy')
    #feat_cc_corr_file2 = os.path.join(subj2_dir, 'plscca',
    #                                  'layer1', 'feat_cc_corr.npy')
    #feat_cc_corr1 = np.load(feat_cc_corr_file1).reshape(96, 11, 11, 10)
    #feat_cc_corr2 = np.load(feat_cc_corr_file2).reshape(96, 11, 11, 10)
    #avg_weights1 = vutil.fweights_top_mean(feat_cc_corr1, 0.2)
    #avg_weights2 = vutil.fweights_top_mean(feat_cc_corr2, 0.2)
    #sim_mtx = corr2_coef(avg_weights1, avg_weights2)
    #np.save('feat_cc_sim_subj_%s_%s.npy'%(subj1_id, subj2_id), sim_mtx)
    pass

def merge_roi_data(cnn_dir, db_dir, subj_id):
    """Merge ROI data for `subj_id`."""
    roi_list = dataio.vim2_roi_info(db_dir, subj_id)
    train_ts = None
    val_ts = None
    vxl_idx = None
    for roi in roi_list:
        idx, tx, vx = dataio.load_vim2_fmri(db_dir, subj_id, roi)
        if not isinstance(train_ts, np.ndarray):
            train_ts = tx
            val_ts = vx
            vxl_idx = idx
        else:
            train_ts = np.vstack((train_ts, tx))
            val_ts = np.vstack((val_ts, vx))
            vxl_idx = np.concatenate((vxl_idx, idx))
    outfile = os.path.join(cnn_dir, 'roi_orig_fmri')
    np.savez(outfile, train_ts=train_ts, val_ts=val_ts, vxl_idx=vxl_idx)


if __name__ == '__main__':
    """Main function."""
    # config parser
    cf = configParser.Config('config')
    # directory config for database
    db_dir = cf.get('database', 'path')
    db_dir = os.path.join(db_dir, 'vim2')
    # directory config for analysis
    root_dir = cf.get('base', 'path')
    feat_dir = os.path.join(root_dir, 'sfeatures', 'vim2', 'caffenet')
    res_dir = os.path.join(root_dir, 'subjects')
 
    #-- general config config
    subj_id = 1
    subj_dir = os.path.join(res_dir, 'vim2_S%s'%(subj_id))
    cnn_dir = os.path.join(subj_dir, 'cnn')
    check_path(cnn_dir)

    # fmri data preparation for ROI-based analysis
    #merge_roi_data(cnn_dir, db_dir, subj_id)
    
    #-- PLS settings
    layer = 'norm1'
    cnum = 20
   
    #-- load cnn feats: data.shape = (channel, x, y, 7200/540)
    train_feat_file = os.path.join(feat_dir, '%s_train_trs.npy'%(layer))
    train_feat_ts = np.load(train_feat_file, mmap_mode='r')
    val_feat_file = os.path.join(feat_dir, '%s_val_trs.npy'%(layer))
    val_feat_ts = np.load(val_feat_file, mmap_mode='r')
 
    #-- fmri data preparation for full-brain analysis
    vxl_idx, train_fmri, val_fmri = dataio.load_vim2_fmri(db_dir, subj_id)
    # 90% data used for model training, 10% data used for component selection
    train_fmri_1 = train_fmri[:, :int(7200*0.9)].T
    train_fmri_2 = train_fmri[:, int(7200*0.9):].T
    val_fmri = val_fmri.T
    train_feat_1 = train_feat_ts[..., :int(7200*0.9)]
    train_feat_1 = train_feat_1.reshape(-1, int(7200*0.9)).T
    train_feat_2 = train_feat_ts[..., int(7200*0.9):]
    train_feat_2 = train_feat_2.reshape(-1, int(7200*0.1)).T
    
    #-- fmri data preparation for ROI-based analysis
    #fmri_file = os.path.join(cnn_dir, 'roi_orig_fmri.npz')
    #fmri_data = np.load(fmri_file)
    ## 90% data used for model training, 10% data used for component selection
    #vxl_idx = fmri_data['vxl_idx']
    #train_fmri_1 = fmri_data['train_ts'][:, :int(7200*0.9)].T
    #train_fmri_2 = fmri_data['train_ts'][:, int(7200*0.9):].T
    #val_fmri = fmri_data['val_ts'].T
    #train_feat_1 = train_feat_ts[..., :int(7200*0.9)]
    #train_feat_1 = train_feat_1.reshape(-1, int(7200*0.9)).T
    #train_feat_2 = train_feat_ts[..., int(7200*0.9):]
    #train_feat_2 = train_feat_2.reshape(-1, int(7200*0.1)).T
    
    #-- PLS model training
    #print 'PLS model initializing ...'
    #pls2 = PLSRegression(n_components=cnum)
    #print 'PLS model training ...'
    #pls2.fit(train_feat_1, train_fmri_1)
    #joblib.dump(pls2,os.path.join(cnn_dir,'%s_pls_model_c%s.pkl'%(layer,cnum)))
    #for i in range(cnum):
    #    print 'Component %s'%(i+1)
    #    print np.corrcoef(pls2.x_scores_[:, i], pls2.y_scores_[:, i])
    ## select component number
    #roi_list = dataio.vim2_roi_info(db_dir, subj_id)
    #idx_dict = {}
    #for roi in roi_list:
    #    roi_idx, tx, vx = dataio.load_vim2_fmri(db_dir, subj_id, roi)
    #    sel_idx = [i for i in range(len(vxl_idx)) if vxl_idx[i] in roi_idx]
    #    if len(sel_idx):
    #        idx_dict[roi] = sel_idx
    #rois = idx_dict.keys()
    #label_file = os.path.join(cnn_dir, '%s_pls_cc_r2_label.csv'%(layer))
    #with open(label_file, 'w+') as f:
    #    for roi in rois:
    #        f.write('%s\n'%(roi))
    #f.close()
    ## eval on testing data
    #roi_r2 = np.zeros((len(rois), cnum))
    #for n in range(cnum):
    #    pred_train_fmri_2 = pls_regression_predict(pls2, train_feat_2, n+1)
    #    err = train_fmri_2 - pred_train_fmri_2
    #    ss_err = np.var(err, axis=0)
    #    ss_tot = np.var(train_fmri_2, axis=0)
    #    pred_r2 = 1 - ss_err/ss_tot
    #    for roi in rois:
    #        roi_r2[rois.index(roi), n] = np.mean(pred_r2[idx_dict[roi]])
    #        print 'C%s - %s : %s'%(n+1, roi, roi_r2[rois.index(roi), n])
    #np.save(os.path.join(cnn_dir, '%s_pls_roi_r2.npy'%(layer)), roi_r2)
    ## eval on validation data
    #roi_r2 = np.zeros((len(rois), cnum))
    #for n in range(cnum):
    #    pred_val_fmri = pls_regression_predict(pls2,
    #                    val_feat_ts.reshape(-1, 540).T, n+1)
    #    err = val_fmri - pred_val_fmri
    #    ss_err = np.var(err, axis=0)
    #    ss_tot = np.var(val_fmri, axis=0)
    #    pred_r2 = 1 - ss_err/ss_tot
    #    for roi in rois:
    #        roi_r2[rois.index(roi), n] = np.mean(pred_r2[idx_dict[roi]])
    #        print 'C%s - %s : %s'%(n+1, roi, roi_r2[rois.index(roi), n])
    #np.save(os.path.join(cnn_dir, '%s_pls_roi_r2_val.npy'%(layer)), roi_r2)

    #-- visualize PLS weights
    #fig_dir = os.path.join(cnn_dir, 'figs')
    #check_path(fig_dir)
    #pls_model_file = os.path.join(cnn_dir,'%s_pls_model_c%s.pkl'%(layer, cnum))
    #pls2 = joblib.load(pls_model_file)
    ## plot feature weights for each component of PLS
    #layer_size = {'norm1': [96, 27, 27],
    #              'norm2': [256, 13, 13],
    #              'conv3': [384, 13, 13],
    #              'conv4': [384, 13, 13],
    #              'pool5': [256, 6, 6],
    #              'fc6': [4096, 1, 1],
    #              'fc7': [4096, 1, 1],
    #              'fc8': [1000, 1, 1]}
    #s = layer_size[layer]
    #xwts = pls2.x_weights_.reshape(s[0], s[1], s[2], -1)
    #vutil.plot_pls_xweights(xwts, fig_dir, '%s_feat_weights'%(layer))
    ## save fmri weights for each component of PLS as nifti file
    #ywts = pls2.y_weights_
    #for c in range(ywts.shape[1]):
    #    vxl_data = ywts[:, c]
    #    outfile =os.path.join(fig_dir,'%s_fmri_weights_c%s.nii.gz'%(layer,c+1))
    #    vutil.vxl_data2nifti(vxl_data, vxl_idx, outfile)

    #-- get the optimal prediction R^2 on validation data
    optimal_cnum = {'norm1': 17, 'norm2': 3, 'conv3': 3, 'conv4': 3,
                    'pool5': 3, 'fc6': 3, 'fc7': 3, 'fc8': 3}
    pls2=joblib.load(os.path.join(cnn_dir,'%s_pls_model_c%s.pkl'%(layer,cnum)))
    pred_val_fmri = pls_regression_predict(pls2, val_feat_ts.reshape(-1,540).T,
                                           optimal_cnum[layer])
    err = val_fmri - pred_val_fmri
    ss_err = np.var(err, axis=0)
    ss_tot = np.var(val_fmri, axis=0)
    pred_r2 = 1 - ss_err/ss_tot
    outfile = os.path.join(cnn_dir, '%s_optimal_pls_val_pred.nii.gz'%(layer))
    vutil.vxl_data2nifti(pred_r2, vxl_idx, outfile)

