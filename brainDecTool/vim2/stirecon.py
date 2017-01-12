# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import sys

# make python use specific caffe version
sys.path.insert(0, '/home/huanglijie/decov/caffe_invert_alexnet/python')
#print sys.path

import caffe
import numpy as np
import os
import scipy.misc
import scipy.io

print(caffe.__file__)

def normalize(img, out_range=(0., 1.), in_range=None):
    """Normalize images.
    i.e. normalize(img, out_range=(0., 1.), in_range=(-120, 120))
    """
    if not in_range:
        min_val = np.min(img)
        max_val = np.max(img)
    else:
        min_val = in_range[0]
        max_val = in_range[1]
    result = np.copy(img)
    result[result>max_val] = max_val
    result[result<min_val] = min_val
    result = (result - min_val) / (max_val - min_val) * (out_range[1] - out_range[0]) + out_range[0]
    return result

def recon_test():
    """Caffe environment test."""
    test_dir = r'/home/huanglijie/decov'
    # set up the inputs for the net:
    batch_size = 10
    image_size = (3, 227, 227)
    images = np.zeros((batch_size,) + image_size, dtype='float32')

    # use crops of the cat image as an example 
    in_image = scipy.misc.imread(os.path.join(test_dir, 'script', 'Cat.jpg'))
    for ni in range(images.shape[0]):
        images[ni] = np.transpose(in_image[ni:ni+image_size[1],
                                           ni:ni+image_size[2]],
                                  (2,0,1))
    # mirror some images to make it a bit more diverse and interesting
    images[::2,:] = images[::2,:,:,::-1]

    # RGB to BGR, because this is what the net wants as input
    data = images[:,::-1] 

    # subtract the ImageNet mean
    matfile = scipy.io.loadmat(os.path.join(test_dir, 'script',
                                            'ilsvrc_2012_mean.mat'))
    image_mean = matfile['image_mean']
    topleft = ((image_mean.shape[0] - image_size[1])/2,
               (image_mean.shape[1] - image_size[2])/2)
    image_mean = image_mean[topleft[0]:topleft[0]+image_size[1],
                            topleft[1]:topleft[1]+image_size[2]]
    del matfile
    # mean is already BGR
    data -= np.expand_dims(np.transpose(image_mean, (2,0,1)), 0)

    # net to extract the features
    caffenet_dir = os.path.join(test_dir, 'caffenet')
    caffenet = caffe.Net(os.path.join(caffenet_dir, 'caffenet_deploy.prototxt'),
                         os.path.join(caffenet_dir, 'caffenet.caffemodel'))
    caffenet.set_mode_cpu() 

    # run caffenet and extract the features
    caffenet.forward(data=data)
    #feat = np.copy(caffenet.blobs['fc6'].data)
    feat = np.copy(caffenet.blobs['norm1'].data)
    #print feat.shape
    del caffenet

    # run the reconstruction net
    rc_dir = os.path.join(test_dir, 'conv1')
    net = caffe.Net(os.path.join(rc_dir,'invert_alexnet_conv1_deploy.prototxt'),
                    os.path.join(rc_dir, 'invert_alexnet_conv1.caffemodel'))
    generated = net.forward(feat=feat)
    recon = generated['deconv0'][:,::-1, :, :]
    del net

    # reorder RGB and normalize images
    images = np.transpose(images, (0, 2, 3, 1))
    recon = np.transpose(recon, (0, 2, 3, 1))
    print images.shape, recon.shape
    normalize(images, out_range=(0., 1.), in_range=(-120, 120))
    normalize(recon, out_range=(0., 1.), in_range=(-120, 120))
    # save results to a file
    np.save('orig_imgs.npy', images)
    np.save('recon_img.npy', recon)

def recon(feat):
    """Reconstruct input images."""
    # run the reconstruction net
    root_dir = r'/home/huanglijie/decov'
    rc_dir = os.path.join(root_dir, 'conv1')
    net = caffe.Net(os.path.join(rc_dir,'invert_alexnet_conv1_deploy.prototxt'),
                    os.path.join(rc_dir, 'invert_alexnet_conv1.caffemodel'))
    generated = net.forward(feat=feat)
    recon = generated['deconv0'][:,::-1, :, :]
    del net

    # reorder RGB and normalize images
    recon = np.transpose(recon, (0, 2, 3, 1))
    print recon.shape
    recon = normalize(recon, out_range=(0., 1.), in_range=(-120, 120))
    return recon

if __name__ == '__main__':
    """Main function."""
    root_dir = r'/home/huanglijie/brainDecoding'
    feat_file = os.path.join(root_dir, 'vS1_pred_feat1.npy')
    feat = np.load(feat_file)
    # up-sample to 27x27
    feat = feat.repeat(2, axis=1).repeat(2, axis=2)
    feat = feat[:, :27, :27, :]
    # reorder data shape
    feat = feat.transpose((3, 0, 1, 2))
    test_feat = feat[:10, ...]
    recon = recon(test_feat)
    # save results to a file
    np.save('recon_img.npy', recon)


