import os, sys
import unittest
from pathlib import Path
from idl2st4dds.createbindings import parse_2_ST

__nocoveralls = False # This might be redundant but just in case ...
try:
    from coveralls import Coveralls
    from coveralls.api import log
except:
    sys.stdout.write('''
#######################################
# 
#   importing "coveralls" failed.
#   
#######################################
''')
    __nocoveralls = True

cur_path = Path(os.getcwd())
idl_path = os.path.join(cur_path, 'idls')
if not os.path.isdir(idl_path):
    idl_path = os.path.join(cur_path.parent.absolute(), 'idls')

class GenerationTestFunctions(unittest.TestCase):
    def setUp(self):
        pass

    def test_module(self):
        
        for filename in os.listdir(idl_path):
            fn = os.path.join(idl_path, filename)
            try:
                res = parse_2_ST(fn, f"{fn}.st")
            except:
                self.assertEqual(filename,"invalid_idl.idl")
                continue
            self.assertEqual(res,True)

if __name__ == '__main__':
    unittest.main()

def suite():
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(GenerationTestFunctions))
    return suite
