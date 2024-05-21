import unittest
import callstack


class CallstackTestCase(unittest.TestCase):

    def test_empty_stack(self):
        in_list = []
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [])  # add assertion here

    def test_f_is_called(self):
        in_list = [("f", "start", 1), ("f", "end", 6)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('f', 5)])  # add assertion here

    def test_f_calls_g(self):
        in_list = [("f", "start", 0), ("g", "start", 2), ("g", "end", 4), ("f", "end", 6)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('g', 2), ('f', 4)])  # add assertion here

    def test_f_calls_g_and_g_calls_h1_and_h2(self):
        in_list = in_list = [("f", "start", 0), ("g", "start", 1), ("h1", "start", 2), ("h1", "end", 3),
                             ("h2", "start", 4),
                             ("h2", "end", 6), ("g", "end", 8), ("f", "end", 10)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('h1', 1), ('h2', 2), ('g', 4), ('f', 3)])  # add assertion here

    def test_f_is_called_then_g_is_called(self):
        in_list = [("f", "start", 0), ("f", "end", 4), ("g", "start", 5), ("g", "end", 6)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('f', 4), ('g', 1)])  # add assertion here

    def test_f_is_called_then_g_is_called_at_the_same_time_f_ends(self):
        in_list = [("f", "start", 0), ("f", "end", 4), ("g", "start", 4), ("g", "end", 6)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('f', 4), ('g', 2)])  # add assertion here

    def test_f_is_called_recursively(self):
        in_list = [("f", "start", 0), ("f", "end", 2), ("f", "start", 1), ("f", "end", 6)]
        out_list = callstack.functions_call_duration(in_list)
        self.assertEqual(out_list, [('f', 1), ('f', 5)])  # add assertion here

    def test_invalid_callstack_case_1(self):
        in_list = [("f", "start", 0), ("g", "end", 1)]
        with self.assertRaises(Exception) as context:
            callstack.functions_call_duration(in_list)
        self.assertTrue('This is not a valid call stack' in str(context.exception))

    def test_invalid_callstack_case_2(self):
        in_list = [("f", "start", 0), ("f", "end", 2), ("g", "start", 1), ("g", "end", 6)]
        with self.assertRaises(Exception) as context:
            callstack.functions_call_duration(in_list)
        self.assertTrue('This is not a valid call stack' in str(context.exception))


if __name__ == '__main__':
    unittest.main()
