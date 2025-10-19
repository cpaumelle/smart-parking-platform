Traceback (most recent call last):
  File "<string>", line 6, in <module>
  File "/usr/local/lib/python3.11/inspect.py", line 1258, in getsource
    lines, lnum = getsourcelines(object)
                  ^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/inspect.py", line 1240, in getsourcelines
    lines, lnum = findsource(object)
                  ^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/inspect.py", line 1077, in findsource
    raise OSError('could not get source code')
OSError: could not get source code
