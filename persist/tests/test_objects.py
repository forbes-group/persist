import inspect

import nose
import mmf.objects

class TestCalcObject(object):
    def test_ordering(self):
        """Test the inherited order of _state_vars."""
        class A(mmf.objects.CalcObject):
            _state_vars = [('c',1),
                           ('d',2)]
        class B(A):
            _state_vars = [('a',1),
                           ('b',2)]
    
        nose.tools.assert_equal(B.class_keys(),['a','b','c','d'])
