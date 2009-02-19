r"""Various Interfaces."""
__all__ = ['Interface', 'IArchivable', 'implements']

try:
    from zope.interface import Interface
    from zope.interface import implements
    
except ImportError:
    class Interface(zope.interface.Interface):        # pragma: no cover 
        """This is a stub allowing the insertion later of an interface
        class.  An interface defines some properties and methods but
        maintains no data and should not be instantiated."""
    def implements(interface):          # pragma: no cover
        pass

class IArchivable(Interface):   # pragma: no cover 
    """Interface for objects that suport archiving."""
    def archive_1(self,env=None):
        """Return (rep,args,imports).
        
        Defines a representation rep of the instance self where the
        instance can be reconstructed from the string rep evaluated in
        the context of args with the specified imports = list of
        (module,iname,uiname) where one has either "import module as
        uiname", "from module import iname" or "from module import
        iname as uiname".
        """
        raise NotImplementedError

