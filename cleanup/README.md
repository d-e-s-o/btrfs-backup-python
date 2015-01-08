cleanup
=======

The **cleanup** module provides primitives aiding in releasing of no
longer used resources in an exception-safe manner. In particular, it defines
``defer``, a function that, when used as a context manager, acts as an object
for registering cleanup functions for acquired resources. An example:

```python
client = Client()
with defer() as d:
  obj = Object()
  d.defer(obj.destroy)
  obj.register(client)
  d.defer(lambda: obj.unregister(client))
  raise Exception()
```

Here, the ``defer`` creates a context object ``d`` that is guaranteed to be
released during block exit (even in the face of exceptions). It is used to
"defer" an invocation of ``obj.destroy`` just after the object got created.
This way, the object is guaranteed to be destroyed properly. Furthermore, the
object is registered with a client. This registration should be undone before
the object vanishes and so another "defer" operation is used to register the
``unregister`` invocation.
This example also illustrates another important fact: execution of the various
cleanup routines happens in reverse order of their registration. This property
is important in most scenarios where resources of interest have dependencies.


Installation
------------

The **cleanup** package does not have any external dependencies. In
order to use it it only needs to be made known to Python, e.g., by
adding the path to the ``src/`` directory to the ``PYTHONPATH``
environment variable.

If you are using [Gentoo Linux](https://www.gentoo.org/), there is an
[ebuild](https://github.com/d-e-s-o/cleanup-ebuild) available that can
be used directly.


Support
-------

The module is tested with Python 3. There is no work going on to
ensure compatibility with Python 2.