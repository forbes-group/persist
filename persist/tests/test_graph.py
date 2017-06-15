from __future__ import print_function

from persist import archive


def test_simple_tuple():
    a = archive.Archive(scoped=False)
    F = ('F', 'F')
    a.insert(F=(F, F))
    g = archive.Graph(a.arch, a.get_persistent_rep, get_id=a.get_id)
    g.reduce()
    assert 1 == len(g.nodes)
