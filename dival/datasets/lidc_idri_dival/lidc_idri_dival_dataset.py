# -*- coding: utf-8 -*-
"""Provides `LIDCIDRIDivalDataset`."""
import os
import json
import numpy as np
from pydicom.filereader import dcmread
from odl.discr.lp_discr import uniform_discr
from dival.datasets.dataset import GroundTruthDataset
from dival.config import CONFIG

# path to LIDC-IDRI
# The public LIDC-IDRI dataset can be downloaded using either the
# NBIA Data Retriever or download_images.py.
DATA_PATH = CONFIG['lidc_idri_dival']['data_path']

if not os.path.isdir(DATA_PATH):
    raise FileNotFoundError(
        'LIDC-IDRI dataset not found: directory "{}" does not exist. You may '
        'need to edit "config.json" (setting "lidc_idri_dival"/"data_path") '
        'and reload dival. The required parts of the LIDC-IDRI dataset must '
        'be stored under this directory. The data can be downloaded either '
        'using the NBIA Data Retriever or by running "datasets/lidc_idri_dival'
        '/download_images.py". Caution: The full dataset is ~135GB, the '
        'required parts that will be stored by download_images.py are still '
        '~30GB. Please make sure there is enough free space.'
        .format(DATA_PATH))

FILE_LIST_FILE = os.path.join(os.path.dirname(__file__),
                              'lidc_idri_file_list.json')


class LIDCIDRIDivalDataset(GroundTruthDataset):
    """Dataset extracted from the `LIDC-IDRI dataset
    <http://doi.org/10.7937/K9/TCIA.2015.LO9QL9SX>`_.

    The selection of image files is determined by the accompanying json file.
    It was generated by the script ``create_file_list.py``.

    Each image is cropped to the centered rectangle of shape (362, 362).
    The values are clipped to [-1024, 3071] HU and optionally (by default)
    normalized into [0., 1.] by the formula
    ``normalized = (original + 1024) / 4096``.
    """
    def __init__(self, normalize=True, min_pt=None, max_pt=None):
        """Construct the ellipses dataset.

        Parameters
        ----------
        normalize : bool, optional
            Whether to normalize the values into [0, 1].
            Default: ``True``.
            If ``False``, the values are in HU and lie in [-1024, 3072].
        min_pt : [int, int], optional
            Minimum values of the lp space. Default: [-181, -181].
        max_pt : [int, int], optional
            Maximum values of the lp space. Default: [181, 181].
        """
        self.normalize = normalize
        self.shape = (362, 362)
        if min_pt is None:
            min_pt = [-self.shape[0]/2, -self.shape[1]/2]
        if max_pt is None:
            max_pt = [self.shape[0]/2, self.shape[1]/2]
        space = uniform_discr(min_pt, max_pt, self.shape, dtype=np.float32)
        with open(FILE_LIST_FILE, 'r') as json_file:
            self.dcm_files_dict = json.load(json_file)
        self.train_len = len(self.dcm_files_dict['train'])
        self.validation_len = len(self.dcm_files_dict['validation'])
        self.test_len = len(self.dcm_files_dict['test'])
        super().__init__(space=space)

    def generator(self, part='train'):
        """Yield selected cropped and normalized LIDC-IDRI images.
        """
        MIN_VAL, MAX_VAL = -1024, 3071

        seed = 42
        if part == 'validation':
            seed = 2
        elif part == 'test':
            seed = 1
        r = np.random.RandomState(seed)
        dcm_files = self.dcm_files_dict[part]
        for dcm_file in dcm_files:
            dataset = dcmread(os.path.join(DATA_PATH, dcm_file))

            # crop to largest rectangle in centered circle
            array = dataset.pixel_array[75:-75, 75:-75].astype(np.float32).T

            # rescale by dicom meta info
            array *= dataset.RescaleSlope
            array += dataset.RescaleIntercept

            # add noise to get continuous values from discrete ones
            array += r.uniform(0., 1., size=array.shape)

            # normalize
            if self.normalize:
                array -= MIN_VAL
                array /= MAX_VAL
                np.clip(array, 0., 1., out=array)
            else:
                np.clip(array, -1024., 3072., out=array)

            image = self.space.element(array)

            yield image