r"""Various Interfaces."""
__all__ = ["IArchivable", "Interface", "implementer", "classImplements"]

import warnings

try:
    from zope.interface import Interface, implementer, classImplements
except ImportError:  # pragma: no cover
    warnings.warn(
        "Could not import zope.interface... using a dummy version."
        + " Interfaces may not work correctly."
    )

    class Interface(object):  # pragma: no cover
        @classmethod
        def providedBy(cls, obj):
            return False

    def implements(*interfaces):
        """Dummy"""

    def implementer(cls, *interfaces):
        """Dummy"""
        return cls

    def classImplements(cls, *interfaces):
        """Dummy"""


class IArchivable(Interface):  # pragma: no cover
    """Interface for objects that support archiving."""

    def get_persistent_rep(env=None):
        """Return `(rep, args, imports)`.

        Define a persistent representation `rep` of the instance self where
        the instance can be reconstructed from the string rep evaluated in the
        context of dict args with the specified imports = list of `(module,
        iname, uiname)` where one has either `import module as uiname`, `from
        module import iname` or `from module import iname as uiname`.
        """
