r"""Provides Archivable class.
"""
__all__ = ['Archivable']

from . import interfaces


###########################################################
# Classes
class Archivable(object):
    r"""Convenience class implementing
    :interface:`interfaces.IArchivable`.

    The user only needs to implement the function :meth:`items`.

    Examples
    --------
    >>> class A(Archivable):
    ...     def __init__(self, a, b):
    ...         self.data = [a, b]
    ...     def items(self):
    ...         return zip(('a', 'b'), self.data)
    >>> a = A(1, 2)
    >>> a
    A(a=1, b=2)
    >>> print(a)
    A(a=1, b=2)
    """

    def items(self):
        r"""Return a list `[(name, obj)]` of `(name, object)` pairs
        where the instance can be constructed as
        `ClassName(name1=obj1, name2=obj2, ...)`.

        The default implementation just uses the elements in
        `self.__dict__`.
        """
        return self.__dict__.items()

    ##########################################
    ##
    def __iter__(self):
        r"""Return an iterator through the archive.

        Examples
        --------
        >>> class A(Archivable):
        ...     def __init__(self, a, b):
        ...         self.data = [a, b]
        ...     def items(self):
        ...         return zip(('a', 'b'), self.data)
        >>> a = A(1, 2)
        >>> for k in a: print(k)
        a
        b
        """
        return (k for (k, v) in self.items())

    def get_persistent_rep(self, env=None):      # pylint: disable-msg=W0613
        r"""Return (rep, args, imports).

        Define a persistent representation `rep` of the instance self where
        the instance can be reconstructed from the string rep evaluated in the
        context of dict args with the specified imports = list of `(module,
        iname, uiname)` where one has either `import module as uiname`, `from
        module import iname` or `from module import iname as uiname`.
        """
        args = dict(self.items())
        module = self.__class__.__module__
        name = self.__class__.__name__
        imports = [(module, name, name)]

        keyvals = ["=".join((k, k)) for k in args]
        rep = "%s(%s)" % (name, ", ".join(keyvals))
        return (rep, args, imports)

    def archive(self, name):
        r"""Return a string representation that can be executed to
        restore the object.

        Examples
        --------
        (Note: We can't actually do this because the class :class:`A`
        cannot be imported from a module if it is defined at the
        interpreter)::

           class A(Archivable):
                def __init__(self, a):
                    self.a = a
                def items(self):
                    return [('a', self.a)]
           a = A(6)            # Create an instance
           s = a.archive('n')  # Get string archive
           env = {}            # Define an environment
           exec(s, env)        # Evaluate the string in env
           o = env['n']        # Access the object from env
           o.a
        """
        from . import archive
        arch = archive.Archive()
        arch.insert(**{name: self})
        return str(arch)

    def __repr__(self):
        from . import archive
        return archive.repr_(self)

    def __str__(self):
        return self.__repr__()


interfaces.classImplements(Archivable, interfaces.IArchivable)


class Container(Archivable):
    """Simple container who's attributes can be specified in the constructor

    >>> Container(a=1, s='Hi')
    Container(a=1, s='Hi')
    """
    def __init__(self, **kw):
        self.__dict__.update(kw)
