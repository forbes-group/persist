r"""Various Interfaces."""
__all__ = ['IArchivable', 'Attribute', 'Interface', 'implements']

import warnings

try:
    from zope.interface import Interface, Attribute
    from zope.interface import implements

except ImportError:
    warnings.warn("Could not import zope.interface... using a dummy version." +
                  " Interfaces may not work correctly.")

    class Interface(object):        # pragma: no cover
        """This is a stub allowing the insertion later of an interface
        class.  An interface defines some properties and methods but
        maintains no data and should not be instantiated."""

        @classmethod
        def providedBy(cls, obj):
            return False

    class Attribute(object):        # pragma: no cover
        """This is a stub allowing the insertion later of an interface
        class.  An interface defines some properties and methods but
        maintains no data and should not be instantiated."""
        def __init__(self, doc):
            self.doc = doc

    def implements(interface):          # pragma: no cover
        pass


class IArchivable(Interface):   # pragma: no cover
    """Interface for objects that support archiving."""
    def get_persistent_rep(env=None):
        """Return `(rep, args, imports)`.

        Define a persistent representation `rep` of the instance self where
        the instance can be reconstructed from the string rep evaluated in the
        context of dict args with the specified imports = list of `(module,
        iname, uiname)` where one has either `import module as uiname`, `from
        module import iname` or `from module import iname as uiname`.
        """
