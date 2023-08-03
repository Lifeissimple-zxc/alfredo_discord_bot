import unittest

from alfredo_lib.local_persistence import cache
from alfredo_lib.local_persistence import models
from alfredo_tests import TEST_CFG

# https://www.youtube.com/watch?v=hV3VIjbr_HE TODO check this out
# Logging config: needs to log to *_test.log file TODO

class TestCache(unittest.TestCase):

    
    @classmethod
    def setUpClass(cls):
        cls._cfg = TEST_CFG["TestCache"] # TODO
        cls._cache = cache.Cache(cls._cfg["db_path"])
    

    def tearDown(self):
        """
        Cleans DB tables
        """
        self._cache._drop_all_tables()

    #TODO parameterize this?
    def test_construct_table_row_ok(self):
        """
        Tests successful scenario of constructing a table row
        """
        exp = models.User(created=1691102774000, username="user_name")
        res, err = self._cache._construct_table_row(dst_attr_name="users_table",
                                                    username="user_name",
                                                    created=1691102774000)
        self.assertEqual(exp.created, res.created)
        self.assertEqual(exp.username, res.username)


if __name__ == "__main__":
    unittest.main()