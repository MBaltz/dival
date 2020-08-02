# -*- coding: utf-8 -*-
"""
Provides the abstract :class:`Measure` base class and some popular measures.

Measure instances are identified by a unique :attr:`~Measure.short_name`, which
is used by the :mod:`~dival.evaluation` module.
"""
from abc import ABC, abstractmethod
from warnings import warn
import numpy as np
from skimage.metrics import structural_similarity
from odl.operator.operator import Operator


def gen_unique_name(name_orig):
    i = 1
    while True:
        yield '{}_{}'.format(name_orig, str(i))
        i += 1


class Measure(ABC):
    """Abstract base class for measures used for evaluation.

    In subclasses, either :meth:`__init__` should be inherited or it should
    call ``super().__init__()`` in order to register the :attr:`short_name`
    and to ensure it is unique.

    Attributes
    ----------
    measure_type : {``'distance'``, ``'quality'``}
        The measure type.
        Measures with type ``'distance'`` should attain small values if the
        reconstruction is good. Measures with type ``'quality'`` should attain
        large values if the reconstruction is good.
    short_name : str
        Short name of the measure, used as identifier (key in
        :attr:`measure_dict`).
    name : str
        Name of the measure.
    description : str
        Description of the measure.
    """
    measure_type = None
    """Class attribute, default value for :attr:`measure_type`."""
    short_name = ''
    """Class attribute, default value for :attr:`short_name`."""
    name = ''
    """Class attribute, default value for :attr:`name`."""
    description = ''
    """Class attribute, default value for :attr:`description`."""

    measure_dict = {}
    """
    Class attribute, registry of all measures with their :attr:`short_name` as
    key.
    """

    def __init__(self, short_name=None):
        """
        Parameters
        ----------
        short_name : str, optional
            The short name of this measure, used as identifier in
            :attr:`measure_dict`.
            If `None` is passed and :attr:`short_name` was not set by the
            subclass, the ``__name__`` of the subclass is used.
            If `short_name` is already taken by another instance, a unique
            short name is generated by appending a suffix of format ``'_%d'``.
        """
        if short_name is not None:
            self.short_name = short_name
        elif self.short_name is None:
            self.short_name = self.__class__.__name__
        if self.short_name in self.__class__.measure_dict:
            old_short_name = self.short_name
            unique_name = gen_unique_name(self.short_name)
            while self.short_name in self.__class__.measure_dict:
                self.short_name = next(unique_name)
            warn("Measure `short_name` '{}' already exists, changed to '{}'"
                 .format(old_short_name, self.short_name))
        self.__class__.measure_dict[self.short_name] = self

    @abstractmethod
    def apply(self, reconstruction, ground_truth):
        """Calculate the value of this measure.

        Parameters
        ----------
        reconstruction : odl element
            The reconstruction.
        ground_truth : odl element
            The ground truth to compare with.

        Returns
        -------
        value : float
            The value of this measure for the given `reconstruction` and
            `ground_truth`.
        """

    def __call__(self, reconstruction, ground_truth):
        """Call :meth:`apply`.
        """
        return self.apply(reconstruction, ground_truth)

    @classmethod
    def get_by_short_name(cls, short_name):
        """
        Return :class:`.Measure` instance with given short name by registry
        lookup.

        Parameters
        ----------
        short_name : str
            Short name, identifier in :attr:`measure_dict`.

        Returns
        -------
        measure : :class:`.Measure`
            The instance.
        """
        return cls.measure_dict.get(short_name)

    class _OperatorForFixedGroundTruth(Operator):
        def __init__(self, measure, ground_truth):
            super().__init__(ground_truth.space, ground_truth.space.field)
            self.measure = measure
            self.ground_truth = ground_truth

        def _call(self, x):
            return self.measure.apply(x, self.ground_truth)

    def as_operator_for_fixed_ground_truth(self, ground_truth):
        """
        Return an odl operator that can be applied to different reconstructions
        for fixed ground truth.

        Returns
        -------
        op : odl operator
            odl operator.
        """
        return self._OperatorForFixedGroundTruth(self, ground_truth)


class L2Measure(Measure):
    """The euclidean (l2) distance measure."""
    measure_type = 'distance'
    short_name = 'l2'
    name = 'euclidean distance'
    description = ('distance given by '
                   'sqrt(sum((reconstruction-ground_truth)**2))')

    def apply(self, reconstruction, ground_truth):
        return np.linalg.norm((np.asarray(reconstruction) -
                               np.asarray(ground_truth)).flat)


L2 = L2Measure()


class MSEMeasure(Measure):
    """The mean squared error distance measure."""
    measure_type = 'distance'
    short_name = 'mse'
    name = 'mean squared error'
    description = ('distance given by '
                   '1/n * sum((reconstruction-ground_truth)**2)')

    def apply(self, reconstruction, ground_truth):
        return np.mean((np.asarray(reconstruction) -
                        np.asarray(ground_truth))**2)


MSE = MSEMeasure()


class PSNRMeasure(Measure):
    """The peak signal-to-noise ratio (PSNR) measure.

    The data range is automatically determined from the ground truth if not
    given to the constructor.

    Attributes
    ----------
    data_range : float or `None`
        The data range (max-min possible value).
        If `data_range` is `None`,
        ``np.max(ground_truth) - np.min(ground_truth)`` is used in
        :meth:`apply`.
    """
    measure_type = 'quality'
    short_name = 'psnr'
    name = 'peak signal-to-noise ratio'
    description = 'quality given by 10*log10(MAX**2/MSE)'

    def __init__(self, data_range=None, short_name=None):
        """
        Parameters
        ----------
        data_range : float, optional
            The data range (max-min possible value).
            If `data_range` is `None`,
            ``np.max(ground_truth) - np.min(ground_truth)`` is used in
            :meth:`apply`.
        short_name : str, optional
            Short name.
        """
        self.data_range = data_range
        if self.data_range is not None and short_name is None:
            short_name = '{}_data_range{}'.format(self.__class__.short_name,
                                                  self.data_range)
        super().__init__(short_name=short_name)

    def apply(self, reconstruction, ground_truth):
        gt = np.asarray(ground_truth)
        mse = np.mean((np.asarray(reconstruction) - gt)**2)
        if mse == 0.:
            return float('inf')
        data_range = self.data_range or (np.max(gt) - np.min(gt))
        return 20*np.log10(data_range) - 10*np.log10(mse)


PSNR = PSNRMeasure()


class SSIMMeasure(Measure):
    """The structural similarity index measure."""
    measure_type = 'quality'
    short_name = 'ssim'
    name = 'structural similarity index'
    description = ('The (M)SSIM like described in `Wang et al. 2014 '
                   '<https://doi.org/10.1109/TIP.2003.819861>`_.')

    def __init__(self, short_name=None, **kwargs):
        """
        This is a wrapper for :func:`skimage.metrics.structural_similarity`.
        The data range is automatically determined from the ground truth if not
        given to the constructor.

        Parameters
        ----------
        short_name : str, optional
            Short name.
        kwargs : dict, optional
            Keyword arguments that will be passed to
            :func:`~skimage.metrics.structural_similarity` in :meth:`apply`.
            If `data_range` is not specified,
            ``np.max(ground_truth) - np.min(ground_truth)`` is used.
        """
        self.kwargs = kwargs
        self.data_range = self.kwargs.pop('data_range', None)
        if self.data_range is not None and short_name is None:
            short_name = '{}_data_range{}'.format(self.__class__.short_name,
                                                  self.data_range)
        super().__init__(short_name=short_name)

    def apply(self, reconstruction, ground_truth):
        gt = np.asarray(ground_truth)
        data_range = (self.data_range if self.data_range is not None
                      else np.max(gt) - np.min(gt))
        return structural_similarity(reconstruction, gt, data_range=data_range,
                            **self.kwargs)


SSIM = SSIMMeasure()
