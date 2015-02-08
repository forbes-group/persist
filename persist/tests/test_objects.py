import nose.tools

from persist import objects


class A(objects.Archivable):
    def __init__(self, x):
        self.x = x

    def items(self):
        return self.__dict__.items()


class TestArchivable(object):
    """Test Archivable class."""

    def test_repr(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)", repr(a))

    def test_str(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)", str(a))

    def test_archive(self):
        """Test the archive method."""
        a = A(6)            # Create an instance
        s = a.archive('n')  # Get string archive
        env = {}            # Define an environment
        exec(s, env)        # Evaluate the string in env
        o = env['n']        # Access the object from env
        nose.tools.assert_equals(o.x, a.x)
