import numpy as np
from ..utils import funcargparse


class ROI(object):
    def __init__(self, imin=0, imax=None, jmin=0, jmax=None):
        object.__init__(self)
        self.imin=imin
        self.imax=imax
        self.jmin=jmin
        self.jmax=jmax
        self._order()

    def _order(self):
        if self.imax is not None:
            self.imin,self.imax=sorted((self.imin,self.imax))
        if self.jmax is not None:
            self.jmin,self.jmax=sorted((self.jmin,self.jmax))
    def _get_limited(self, shape=None):
        if shape is None:
            if self.imax is None or self.jmax is None:
                raise ValueError("one of the ROI dimensions is unconstrained")
            return self.imin,self.imax,self.jmin,self.jmax
        imin=max(self.imin,0)
        imax=shape[0] if self.imax is None else min(self.imax,shape[0])
        jmin=max(self.jmin,0)
        jmax=shape[1] if self.jmax is None else min(self.jmax,shape[1])
        return sorted((imin,imax))+sorted((jmin,jmax))

    def copy(self):
        return ROI(self.imin,self.imax,self.jmin,self.jmax)

    def center(self, shape=None):
        imin,imax,jmin,jmax=self._get_limited(shape)
        return (imin+imax)/2, (jmin+jmax)/2
    def size(self, shape=None):
        imin,imax,jmin,jmax=self._get_limited(shape)
        return (imax-imin), (jmax-jmin)
    def area(self, shape=None):
        size=self.size(shape)
        return size[0]*size[1]
    def tup(self, shape=None):
        return self._get_limited(shape)
    def ispan(self, shape=None):
        return self.tup(shape)[0:2]
    def jspan(self, shape=None):
        return self.tup(shape)[2:4]

    @classmethod
    def from_centersize(cls, center, size, shape=None):
        size=funcargparse.as_sequence(size,2)
        imin,imax=center[0]-abs(size[0])//2,center[0]+(abs(size[0])+1)//2
        jmin,jmax=center[1]-abs(size[1])//2,center[1]+(abs(size[1])+1)//2
        res=cls(imin,imax,jmin,jmax)
        if shape is not None:
            res.limit(shape)
        return res

    def limit(self, shape):
        self.imin,self.imax,self.jmin,self.jmax=self._get_limited(shape)
        return self



def get_region_sum(image, center, size):
    """
    Sum part of the image with the given center and size (both are tuples ``(i, j)``).
    The region is automatically reduced if a part of it is outside of the image.

    Return tuple ``(sum, area)``, where area is the acual summer region are (in pixels).
    """
    roi=ROI.from_centersize(center,size,shape=image.shape)
    ispan,jspan=roi.ispan(),roi.jspan()
    return np.sum(image[ispan[0]:ispan[1],jspan[0]:jspan[1]]), roi.area()