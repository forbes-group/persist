import os.path
import shutil
import tempfile

import pytest


@pytest.fixture(params=['npy', 'npz', 'hdf5'])
def data_format(request):
    yield request.param


@pytest.fixture
def ds_name():
    ds_name = tempfile.mkdtemp(dir='.')[2:]
    os.rmdir(ds_name)
    yield ds_name
    if os.path.exists(ds_name):
        shutil.rmtree(ds_name)


@pytest.fixture
def datafile():
    f, filename = tempfile.mkstemp()
    os.close(f)
    os.remove(filename)
    yield filename
    if os.path.exists(filename):
        if os.path.isfile(filename):
            os.remove(filename)
        else:
            shutil.rmtree(filename)


@pytest.fixture
def hdf5_datafile():
    with tempfile.NamedTemporaryFile(suffix='.hd5', delete=True) as f:
        yield f.name


@pytest.fixture
def npz_datafile():
    with tempfile.NamedTemporaryFile(suffix='.npz', delete=True) as f:
        yield f.name


@pytest.fixture
def datadir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def npy_datafile():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def np():
    try:
        import numpy
        numpy.random.seed(3)
        return numpy
    except ImportError:         # pragma: no cover
        pytest.skip("Skipping test that depends on numpy")


@pytest.fixture
def sp():
    try:
        import scipy
        return scipy
    except ImportError:         # pragma: no cover
        pytest.skip("Skipping test that depends on scipy")


@pytest.fixture
def h5py():
    try:
        import h5py
        return h5py
    except ImportError:         # pragma: no cover
        pytest.skip("Skipping test that depends on h5py")


@pytest.fixture(params=[True, False])
def scoped(request):
    yield request.param
