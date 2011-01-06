#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "structmember.h"

#define _MULTIARRAYMODULE
#include <numpy/ndarrayobject.h>

#include "npy_config.h"

#include "numpy/npy_3kcompat.h"

#include "new_iterator.h"

typedef struct NewNpyArrayIterObject_tag NewNpyArrayIterObject;

struct NewNpyArrayIterObject_tag {
    PyObject_HEAD
    /* The iterator */
    NpyIter *iter;
    /* Flag indicating iteration started/stopped */
    char started, finished;
    /* Child to update for nested iteration */
    NewNpyArrayIterObject *nested_child;
    /* Cached values from the iterator */
    NpyIter_IterNext_Fn iternext;
    NpyIter_GetCoords_Fn getcoords;
    char **dataptrs;
    PyArray_Descr **dtypes;
    PyArrayObject **objects;
    npy_intp *innerstrides, *innerloopsizeptr;
    char readflags[NPY_MAXARGS];
    char writeflags[NPY_MAXARGS];
};

void npyiter_cache_values(NewNpyArrayIterObject *self)
{
    NpyIter *iter = self->iter;

    /* iternext and getcoords functions */
    self->iternext = NpyIter_GetIterNext(iter);
    if (NpyIter_HasCoords(iter)) {
        self->getcoords = NpyIter_GetGetCoords(iter);
    }
    else {
        self->getcoords = NULL;
    }

    /* Internal data pointers */
    self->dataptrs = NpyIter_GetDataPtrArray(iter);
    self->dtypes = NpyIter_GetDescrArray(iter);
    self->objects = NpyIter_GetObjectArray(iter);

    if (NpyIter_HasInnerLoop(iter)) {
        self->innerstrides = NULL;
        self->innerloopsizeptr = NULL;
    }
    else {
        self->innerstrides = NpyIter_GetInnerStrideArray(iter);
        self->innerloopsizeptr = NpyIter_GetInnerLoopSizePtr(iter);
    }

    /* The read/write settings */
    NpyIter_GetReadFlags(iter, self->readflags);
    NpyIter_GetWriteFlags(iter, self->writeflags);
}

static PyObject *
npyiter_new(PyTypeObject *subtype, PyObject *args, PyObject *kwds)
{
    NewNpyArrayIterObject *self;

    self = (NewNpyArrayIterObject *)subtype->tp_alloc(subtype, 0);
    if (self != NULL) {
        self->iter = NULL;
        self->nested_child = NULL;
    }

    return (PyObject *)self;
}

static int
NpyIter_GlobalFlagsConverter(PyObject *flags_in, npy_uint32 *flags)
{
    npy_uint32 tmpflags = 0;
    int iflags, nflags;

    PyObject *f;
    char *str = NULL;
    Py_ssize_t length = 0;
    npy_uint32 flag = 0;

    if (flags_in == NULL || flags_in == Py_None) {
        *flags = 0;
        return NPY_SUCCEED;
    }

    if (!PyTuple_Check(flags_in) && !PyList_Check(flags_in)) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator global flags must be a list or tuple of strings");
        return NPY_FAIL;
    }

    nflags = PySequence_Size(flags_in);

    for (iflags = 0; iflags < nflags; ++iflags) {
        f = PySequence_GetItem(flags_in, iflags);
        if (f == NULL) {
            return NPY_FAIL;
        }
        if (PyString_AsStringAndSize(f, &str, &length) == -1) {
            Py_DECREF(f);
            return NPY_FAIL;
        }
        /* Use switch statements to quickly isolate the right flag */
        switch (str[0]) {
            case 'b':
                if (strcmp(str, "buffered") == 0) {
                    flag = NPY_ITER_BUFFERED;
                }
                break;
            case 'c':
                if (length >= 6) switch (str[5]) {
                    case 'e':
                        if (strcmp(str, "c_index") == 0) {
                            flag = NPY_ITER_C_INDEX;
                        }
                        break;
                    case 's':
                        if (strcmp(str, "coords") == 0) {
                            flag = NPY_ITER_COORDS;
                        }
                        break;
                    case 'n':
                        if (strcmp(str, "common_dtype") == 0) {
                            flag = NPY_ITER_COMMON_DTYPE;
                        }
                        break;
                }
                break;
            case 'f':
                if (strcmp(str, "f_index") == 0) {
                    flag = NPY_ITER_F_INDEX;
                }
                break;
            case 'g':
                if (strcmp(str, "growinner") == 0) {
                    flag = NPY_ITER_GROWINNER;
                }
                break;
            case 'n':
                if (strcmp(str, "no_inner_iteration") == 0) {
                    flag = NPY_ITER_NO_INNER_ITERATION;
                }
                break;
            case 'r':
                if (strcmp(str, "ranged") == 0) {
                    flag = NPY_ITER_RANGED;
                }
                break;
        }
        if (flag == 0) {
            PyErr_Format(PyExc_ValueError,
                    "Unexpected iterator global flag \"%s\"", str);
            Py_DECREF(f);
            return NPY_FAIL;
        }
        else {
            tmpflags |= flag;
        }
        Py_DECREF(f);
    }

    *flags |= tmpflags;
    return NPY_SUCCEED;
}

/* TODO: Use PyArray_OrderConverter once 'K' is added there */
static int
npyiter_order_converter(PyObject *order_in, NPY_ORDER *order)
{
    char *str = NULL;
    Py_ssize_t length = 0;
    
    if (PyString_AsStringAndSize(order_in, &str, &length) == -1) {
        return NPY_FAIL;
    }

    if (length == 1) switch (str[0]) {
        case 'C':
            *order = NPY_CORDER;
            return NPY_SUCCEED;
        case 'F':
            *order = NPY_FORTRANORDER;
            return NPY_SUCCEED;
        case 'A':
            *order = NPY_ANYORDER;
            return NPY_SUCCEED;
        case 'K':
            *order = NPY_KEEPORDER;
            return NPY_SUCCEED;
    }

    PyErr_SetString(PyExc_ValueError,
            "order must be one of 'C', 'F', 'A', or 'K'");
    return NPY_FAIL;
}

/*
 * Convert any Python object, *obj*, to an NPY_CASTING enum.
 * TODO: Move elsewhere, add to the NumPy API.
 */
static int
PyArray_CastingConverter(PyObject *obj, NPY_CASTING *casting)
{
    char *str = NULL;
    Py_ssize_t length = 0;
    
    if (PyString_AsStringAndSize(obj, &str, &length) == -1) {
        return NPY_FAIL;
    }
    if (length >= 2) switch (str[2]) {
        case 0:
            if (strcmp(str, "no") == 0) {
                *casting = NPY_NO_CASTING;
                return NPY_SUCCEED;
            }
            break;
        case 'u':
            if (strcmp(str, "equiv") == 0) {
                *casting = NPY_EQUIV_CASTING;
                return NPY_SUCCEED;
            }
            break;
        case 'f':
            if (strcmp(str, "safe") == 0) {
                *casting = NPY_SAFE_CASTING;
                return NPY_SUCCEED;
            }
            break;
        case 'm':
            if (strcmp(str, "same_kind") == 0) {
                *casting = NPY_SAME_KIND_CASTING;
                return NPY_SUCCEED;
            }
            break;
        case 's':
            if (strcmp(str, "unsafe") == 0) {
                *casting = NPY_UNSAFE_CASTING;
                return NPY_SUCCEED;
            }
            break;
    }

    PyErr_SetString(PyExc_ValueError,
            "casting must be one of 'no', 'equiv', 'safe', "
            "'same_kind', or 'unsafe'");
    return NPY_FAIL;

}

static int
NpyIter_OpFlagsConverter(PyObject *op_flags_in,
                         npy_uint32 *op_flags)
{
    int iflags, nflags;

    if (!PyTuple_Check(op_flags_in) && !PyList_Check(op_flags_in)) {
        PyErr_SetString(PyExc_ValueError,
                "op_flags must be a tuple or array of per-op flag-tuples");
        return NPY_FAIL;
    }

    nflags = PySequence_Size(op_flags_in);

    *op_flags = 0;
    for (iflags = 0; iflags < nflags; ++iflags) {
        PyObject *f;
        char *str = NULL;
        Py_ssize_t length = 0;
        npy_uint32 flag = 0;

        f = PySequence_GetItem(op_flags_in, iflags);
        if (f == NULL) {
            return NPY_FAIL;
        }

        if (PyString_AsStringAndSize(f, &str, &length) == -1) {
            Py_DECREF(f);
            PyErr_SetString(PyExc_ValueError,
                   "op_flags must be a tuple or array of per-op flag-tuples");
            return NPY_FAIL;
        }

        /* Use switch statements to quickly isolate the right flag */
        switch (str[0]) {
            case 'a':
                if (strcmp(str, "allocate") == 0) {
                    flag = NPY_ITER_ALLOCATE;
                }
                break;
            case 'c':
                if (strcmp(str, "copy") == 0) {
                    flag = NPY_ITER_COPY;
                }
                break;
            case 'n':
                switch (str[1]) {
                    case 'b':
                        if (strcmp(str, "nbo_aligned") == 0) {
                            flag = NPY_ITER_NBO_ALIGNED;
                        }
                        break;
                    case 'o':
                        if (strcmp(str, "no_subtype") == 0) {
                            flag = NPY_ITER_NO_SUBTYPE;
                        }
                        else if (strcmp(str, "no_broadcast") == 0) {
                            flag = NPY_ITER_NO_BROADCAST;
                        }
                        break;
                }
                break;
            case 'r':
                if (length > 4) switch (str[4]) {
                    case 'o':
                        if (strcmp(str, "readonly") == 0) {
                            flag = NPY_ITER_READONLY;
                        }
                        break;
                    case 'w':
                        if (strcmp(str, "readwrite") == 0) {
                            flag = NPY_ITER_READWRITE;
                        }
                        break;
                }
                break;
            case 'u':
                if (strcmp(str, "updateifcopy") == 0) {
                    flag = NPY_ITER_UPDATEIFCOPY;
                }
                break;
            case 'w':
                if (length > 5) switch (str[5]) {
                    case 'a':
                        if (strcmp(str,
                                        "writeable_references") == 0) {
                            flag = NPY_ITER_WRITEABLE_REFERENCES;
                        }
                        break;
                    case 'o':
                        if (strcmp(str, "writeonly") == 0) {
                            flag = NPY_ITER_WRITEONLY;
                        }
                        break;
                }
                break;
        }
        if (flag == 0) {
            PyErr_Format(PyExc_ValueError,
                    "Unexpected per-op iterator flag \"%s\"", str);
            Py_DECREF(f);
            return NPY_FAIL;
        }
        else {
            *op_flags |= flag;
        }
        Py_DECREF(f);
    }

    return NPY_SUCCEED;
}

static int
npyiter_convert_op_flags_array(PyObject *op_flags_in,
                         npy_uint32 *op_flags_array, npy_intp niter)
{
    npy_intp iiter;

    if (!PyTuple_Check(op_flags_in) && !PyList_Check(op_flags_in)) {
        PyErr_SetString(PyExc_ValueError,
                "op_flags must be a tuple or array of per-op flag-tuples");
        return NPY_FAIL;
    }

    if (PySequence_Size(op_flags_in) != niter) {
        goto try_single_flags;
    }

    for (iiter = 0; iiter < niter; ++iiter) {
        PyObject *f = PySequence_GetItem(op_flags_in, iiter);
        if (f == NULL) {
            return NPY_FAIL;
        }
        if (NpyIter_OpFlagsConverter(f,
                        &op_flags_array[iiter]) != NPY_SUCCEED) {
            Py_DECREF(f);
            /* If the first one doesn't work, try the whole thing as flags */
            if (iiter == 0) {
                PyErr_Clear();
                goto try_single_flags;
            }
            return NPY_FAIL;
        }
        
        Py_DECREF(f);
    }

    return NPY_SUCCEED;

try_single_flags:
    if (NpyIter_OpFlagsConverter(op_flags_in,
                        &op_flags_array[0]) != NPY_SUCCEED) {
        return NPY_FAIL;
    }

    for (iiter = 1; iiter < niter; ++iiter) {
        op_flags_array[iiter] = op_flags_array[0];
    }

    return NPY_SUCCEED;
}

static int
npyiter_convert_dtypes(PyObject *op_dtypes_in,
                        PyArray_Descr **op_dtypes,
                        npy_intp niter)
{
    npy_intp iiter;

    /*
     * If the input isn't a tuple of dtypes, try converting it as-is
     * to a dtype, and replicating to all operands.
     */
    if ((!PyTuple_Check(op_dtypes_in) && !PyList_Check(op_dtypes_in)) ||
                                    PySequence_Size(op_dtypes_in) != niter) {
        goto try_single_dtype;
    }

    for (iiter = 0; iiter < niter; ++iiter) {
        PyObject *dtype = PySequence_GetItem(op_dtypes_in, iiter);
        if (dtype == NULL) {
            npy_intp i;
            for (i = 0; i < iiter; ++i ) {
                Py_XDECREF(op_dtypes[i]);
            }
            return NPY_FAIL;
        }

        /* Try converting the object to a descr */
        if (PyArray_DescrConverter2(dtype, &op_dtypes[iiter]) != NPY_SUCCEED) {
            npy_intp i;
            for (i = 0; i < iiter; ++i ) {
                Py_XDECREF(op_dtypes[i]);
            }
            Py_DECREF(dtype);
            PyErr_Clear();
            goto try_single_dtype;
        }

        Py_DECREF(dtype);
    }

    return NPY_SUCCEED;

try_single_dtype:
    if (PyArray_DescrConverter2(op_dtypes_in, &op_dtypes[0]) == NPY_SUCCEED) {
        for (iiter = 1; iiter < niter; ++iiter) {
            op_dtypes[iiter] = op_dtypes[0];
            Py_XINCREF(op_dtypes[iiter]);
        }
        return NPY_SUCCEED;
    }

    return NPY_FAIL;
}

static int
npyiter_convert_op_axes(PyObject *op_axes_in, npy_intp niter,
                        npy_intp **op_axes, npy_intp *oa_ndim)
{
    PyObject *a;
    npy_intp iiter;

    if ((!PyTuple_Check(op_axes_in) && !PyList_Check(op_axes_in)) ||
                                PySequence_Size(op_axes_in) != niter) {
        PyErr_SetString(PyExc_ValueError,
                "op_axes must be a tuple/list matching the number of ops");
        return NPY_FAIL;
    }

    *oa_ndim = 0;

    /* Copy the tuples into op_axes */
    for (iiter = 0; iiter < niter; ++iiter) {
        npy_intp idim;
        a = PySequence_GetItem(op_axes_in, iiter);
        if (a == NULL) {
            return NPY_FAIL;
        }
        if (a == Py_None) {
            op_axes[iiter] = NULL;
        } else {
            if (!PyTuple_Check(a) && !PyList_Check(a)) {
                PyErr_SetString(PyExc_ValueError,
                        "Each entry of op_axes must be None "
                        "or a tuple/list");
                Py_DECREF(a);
                return NPY_FAIL;
            }
            if (*oa_ndim == 0) {
                *oa_ndim = PySequence_Size(a);
                if (*oa_ndim == 0) {
                    PyErr_SetString(PyExc_ValueError,
                            "op_axes must have at least one dimension");
                    return NPY_FAIL;
                }
                if (*oa_ndim > NPY_MAXDIMS) {
                    PyErr_SetString(PyExc_ValueError,
                            "Too many dimensions in op_axes");
                    return NPY_FAIL;
                }
            }
            if (PySequence_Size(a) != *oa_ndim) {
                PyErr_SetString(PyExc_ValueError,
                        "Each entry of op_axes must have the same size");
                Py_DECREF(a);
                return NPY_FAIL;
            }
            for (idim = 0; idim < *oa_ndim; ++idim) {
                PyObject *v = PySequence_GetItem(a, idim);
                if (v == NULL) {
                    Py_DECREF(a);
                    return NPY_FAIL;
                }
                /* numpy.newaxis is None */
                if (v == Py_None) {
                    op_axes[iiter][idim] = -1;
                }
                else {
                    op_axes[iiter][idim] = PyInt_AsLong(v);
                    if (op_axes[iiter][idim]==-1 &&
                                                PyErr_Occurred()) {
                        Py_DECREF(a);
                        Py_DECREF(v);
                        return NPY_FAIL;
                    }
                }
                Py_DECREF(v);
            }
            Py_DECREF(a);
        }
    }

    if (*oa_ndim == 0) {
        PyErr_SetString(PyExc_ValueError,
                "If op_axes is provided, at least one list of axes "
                "must be contained within it");
        return NPY_FAIL;
    }
    
    return NPY_SUCCEED;
}

/*
 * Converts the operand array and op_flags array into the form NpyIter_MultiNew
 * needs.  Sets niter, and on success, each op[i] owns a reference
 * to an array object.
 */
static int
npyiter_convert_ops(PyObject *op_in, PyObject *op_flags_in,
                    PyArrayObject **op, npy_uint32 *op_flags,
                    npy_intp *niter_out)
{
    npy_intp iiter, niter;

    /* niter and op */
    if (PyTuple_Check(op_in) || PyList_Check(op_in)) {
        niter = PySequence_Size(op_in);
        if (niter == 0) {
            PyErr_SetString(PyExc_ValueError,
                    "Must provide at least one operand");
            return NPY_FAIL;
        }
        if (niter > NPY_MAXARGS) {
            PyErr_SetString(PyExc_ValueError, "Too many operands");
            return NPY_FAIL;
        }
    
        for (iiter = 0; iiter < niter; ++iiter) {
            PyObject *item = PySequence_GetItem(op_in, iiter);
            if (item == NULL) {
                npy_intp i;
                for (i = 0; i < iiter; ++i) {
                    Py_XDECREF(op[i]);
                }
                return NPY_FAIL;
            }
            else if (item == Py_None) {
                Py_DECREF(item);
                item = NULL;
            }
            /* This is converted to an array after op flags are retrieved */
            op[iiter] = (PyArrayObject *)item;
        }
    }
    else {
        niter = 1;
        /* Is converted to an array after op flags are retrieved */
        Py_INCREF(op_in);
        op[0] = (PyArrayObject *)op_in;
    }

    *niter_out = niter;

    /* op_flags */
    if (op_flags_in == NULL || op_flags_in == Py_None) {
        for (iiter = 0; iiter < niter; ++iiter) {
            /*
             * By default, make NULL operands writeonly and flagged for
             * allocation, writeable arrays readwrite, and anything
             * else readonly.
             */
            if (op[iiter] == NULL) {
                op_flags[iiter] = NPY_ITER_WRITEONLY | NPY_ITER_ALLOCATE;
            }
            else if (PyArray_Check(op[iiter]) &&
                            PyArray_CHKFLAGS(op[iiter], NPY_WRITEABLE)) {
                op_flags[iiter] = NPY_ITER_READWRITE;
            }
            else {
                op_flags[iiter] = NPY_ITER_READONLY;
            }
        }
    }
    else if (npyiter_convert_op_flags_array(op_flags_in,
                                      op_flags, niter) != NPY_SUCCEED) {
        for (iiter = 0; iiter < niter; ++iiter) {
            Py_XDECREF(op[iiter]);
        }
        return NPY_FAIL;
    }

    /* Now that we have the flags - convert all the ops to arrays */
    for (iiter = 0; iiter < niter; ++iiter) {
        if (op[iiter] != NULL) {
            PyArrayObject *ao;
            int fromanyflags = 0;
            
            if (op_flags[iiter]&(NPY_ITER_READWRITE|NPY_ITER_WRITEONLY)) {
                fromanyflags = NPY_UPDATEIFCOPY;
            }
            ao = (PyArrayObject *)PyArray_FromAny((PyObject *)op[iiter],
                                            NULL, 0, 0, fromanyflags, NULL);
            if (ao == NULL) {
                if (PyErr_Occurred() &&
                            PyErr_ExceptionMatches(PyExc_TypeError)) {
                    PyErr_SetString(PyExc_TypeError,
                            "Iterator operand is flagged as writeable, "
                            "but is an object which cannot be written "
                            "back to via UPDATEIFCOPY");
                }
                for (iiter = 0; iiter < niter; ++iiter) {
                    Py_DECREF(op[iiter]);
                }
                return NPY_FAIL;
            }
            Py_DECREF(op[iiter]);
            op[iiter] = ao;
        }
    }

    return NPY_SUCCEED;
}

static int
npyiter_init(NewNpyArrayIterObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"op", "flags", "op_flags", "op_dtypes",
                             "order", "casting", "op_axes", "buffersize",
                             NULL};

    PyObject *op_in = NULL, *flags_in = NULL, *op_flags_in = NULL,
                *op_dtypes_in = NULL, *op_axes_in = NULL;

    npy_intp iiter, niter = 0;
    PyArrayObject *op[NPY_MAXARGS];
    npy_uint32 flags = 0;
    NPY_ORDER order = NPY_KEEPORDER;
    NPY_CASTING casting = NPY_SAFE_CASTING;
    npy_uint32 op_flags[NPY_MAXARGS];
    PyArray_Descr *op_request_dtypes[NPY_MAXARGS];
    npy_intp oa_ndim = 0;
    npy_intp op_axes_arrays[NPY_MAXARGS][NPY_MAXDIMS];
    npy_intp *op_axes[NPY_MAXARGS];
    int buffersize = 0;

    if (self->iter != NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator was already initialized");
        return -1;
    }

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|OOOO&O&Oi", kwlist,
                    &op_in,
                    &flags_in,
                    &op_flags_in,
                    &op_dtypes_in,
                    npyiter_order_converter, &order,
                    PyArray_CastingConverter, &casting,
                    &op_axes_in,
                    &buffersize)) {
        return -1;
    }

    /* flags */
    if (NpyIter_GlobalFlagsConverter(flags_in, &flags) != NPY_SUCCEED) {
        return -1;
    }

    /* op and op_flags */
    if (npyiter_convert_ops(op_in, op_flags_in, op, op_flags, &niter)
                                                        != NPY_SUCCEED) {
        return -1;
    }

    /* Set the dtypes to all NULL to start as well */
    memset(op_request_dtypes, 0, sizeof(op_request_dtypes[0])*niter);

    /* op_request_dtypes */
    if (op_dtypes_in != NULL && op_dtypes_in != Py_None &&
            npyiter_convert_dtypes(op_dtypes_in,
                                   op_request_dtypes, niter) != NPY_SUCCEED) {
        goto fail;
    }

    /* op_axes */
    if (op_axes_in != NULL && op_axes_in != Py_None) {
        /* Initialize to point to the op_axes arrays */
        for (iiter = 0; iiter < niter; ++iiter) {
            op_axes[iiter] = op_axes_arrays[iiter];
        }

        if (npyiter_convert_op_axes(op_axes_in, niter,
                                    op_axes, &oa_ndim) != NPY_SUCCEED) {
            goto fail;
        }
    }

    self->iter = NpyIter_MultiNew(niter, op, flags, order, casting, op_flags,
                                  op_request_dtypes,
                                  oa_ndim, oa_ndim > 0 ? op_axes : NULL,
                                  buffersize);

    if (self->iter == NULL) {
        goto fail;
    }

    /* Cache some values for the member functions to use */
    npyiter_cache_values(self);

    self->started = 0;
    self->finished = 0;

    /* Release the references we got to the ops and dtypes */
    for (iiter = 0; iiter < niter; ++iiter) {
        Py_XDECREF(op[iiter]);
        Py_XDECREF(op_request_dtypes[iiter]);
    }

    return 0;

fail:
    for (iiter = 0; iiter < niter; ++iiter) {
        Py_XDECREF(op[iiter]);
        Py_XDECREF(op_request_dtypes[iiter]);
    }
    return -1;
}

NPY_NO_EXPORT PyObject *
NpyIter_NestedIters(PyObject *NPY_UNUSED(self),
                    PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"op", "axes", "flags", "op_flags",
                             "op_dtypes", "order",
                             "casting", "buffersize",
                             NULL};

    PyObject *op_in = NULL, *axes_in = NULL, *flags_in = NULL,
            *op_flags_in = NULL, *op_dtypes_in = NULL;

    npy_intp iiter, niter = 0, inest, nnest = 0;
    PyArrayObject *op[NPY_MAXARGS];
    npy_uint32 flags = 0, flags_inner = 0;
    NPY_ORDER order = NPY_KEEPORDER;
    NPY_CASTING casting = NPY_SAFE_CASTING;
    npy_uint32 op_flags[NPY_MAXARGS], op_flags_inner[NPY_MAXARGS];
    PyArray_Descr *op_request_dtypes[NPY_MAXARGS],
                  *op_request_dtypes_inner[NPY_MAXARGS];
    npy_intp op_axes_data[NPY_MAXDIMS];
    npy_intp *nested_op_axes[NPY_MAXDIMS];
    npy_intp nested_naxes[NPY_MAXDIMS], iaxes, naxes;
    npy_intp negones[NPY_MAXDIMS];
    char used_axes[NPY_MAXDIMS];
    int buffersize = 0;

    PyObject *ret = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO|OOOO&O&i", kwlist,
                    &op_in,
                    &axes_in,
                    &flags_in,
                    &op_flags_in,
                    &op_dtypes_in,
                    npyiter_order_converter, &order,
                    PyArray_CastingConverter, &casting,
                    &buffersize)) {
        return NULL;
    }

    /* axes */
    if (!PyTuple_Check(axes_in) && !PyList_Check(axes_in)) {
        PyErr_SetString(PyExc_ValueError,
                "axes must be a tuple of axis arrays");
        return NULL;
    }
    nnest = PySequence_Size(axes_in);
    if (nnest < 2) {
        PyErr_SetString(PyExc_ValueError,
                "axes must have at least 2 entries for nested iteration");
        return NULL;
    }
    naxes = 0;
    memset(used_axes, 0, NPY_MAXDIMS);
    for (inest = 0; inest < nnest; ++inest) {
        PyObject *item = PySequence_GetItem(axes_in, inest);
        npy_intp i;
        if (item == NULL) {
            return NULL;
        }
        if (!PyTuple_Check(item) && !PyList_Check(item)) {
            PyErr_SetString(PyExc_ValueError,
                    "Each item in axes must be a an integer tuple");
            Py_DECREF(item);
            return NULL;
        }
        nested_naxes[inest] = PySequence_Size(item);
        if (naxes + nested_naxes[inest] > NPY_MAXDIMS) {
            PyErr_SetString(PyExc_ValueError,
                    "Too many axes given");
            Py_DECREF(item);
            return NULL;
        }
        for (i = 0; i < nested_naxes[inest]; ++i) {
            PyObject *v = PySequence_GetItem(item, i);
            npy_intp axis;
            if (v == NULL) {
                Py_DECREF(item);
                return NULL;
            }
            axis = PyInt_AsLong(v);
            Py_DECREF(v);
            if (axis < 0 || axis >= NPY_MAXDIMS) {
                PyErr_SetString(PyExc_ValueError,
                        "An axis is out of bounds");
                Py_DECREF(item);
                return NULL;
            }
            /*
             * This check is very important, without it out of bounds
             * data accesses are possible.
             */
            if (used_axes[axis] != 0) {
                PyErr_SetString(PyExc_ValueError,
                        "An axis is used more than once");
                Py_DECREF(item);
                return NULL;
            }
            used_axes[axis] = 1;
            op_axes_data[naxes+i] = axis;
        }
        nested_op_axes[inest] = &op_axes_data[naxes];
        naxes += nested_naxes[inest];
        Py_DECREF(item);
    }

    /* flags */
    if (NpyIter_GlobalFlagsConverter(flags_in, &flags) != NPY_SUCCEED) {
        return NULL;
    }

    /* op and op_flags */
    if (npyiter_convert_ops(op_in, op_flags_in, op, op_flags, &niter)
                                                        != NPY_SUCCEED) {
        return NULL;
    }

    /* Set the dtypes to all NULL to start as well */
    memset(op_request_dtypes, 0, sizeof(op_request_dtypes[0])*niter);
    memset(op_request_dtypes_inner, 0,
                        sizeof(op_request_dtypes_inner[0])*niter);

    /* op_request_dtypes */
    if (op_dtypes_in != NULL && op_dtypes_in != Py_None &&
            npyiter_convert_dtypes(op_dtypes_in,
                                   op_request_dtypes, niter) != NPY_SUCCEED) {
        goto fail;
    }

    ret = PyTuple_New(nnest);
    if (ret == NULL) {
        goto fail;
    }

    /* For broadcasting allocated arrays */
    for (iaxes = 0; iaxes < naxes; ++iaxes) {
        negones[iaxes] = -1;
    }

    /*
     * Clear any unnecessary ALLOCATE flags, so we can use them
     * to indicate exactly the allocated outputs.  Also, separate
     * the inner loop flags.
     */
    for (iiter = 0; iiter < niter; ++iiter) {
        if ((op_flags[iiter]&NPY_ITER_ALLOCATE) && op[iiter] != NULL) {
            op_flags[iiter] &= ~NPY_ITER_ALLOCATE;
        }

        /*
         * Clear any flags allowing copies or output allocation for
         * the inner loop.
         */
        op_flags_inner[iiter] = op_flags[iiter] & ~(NPY_ITER_COPY|
                             NPY_ITER_UPDATEIFCOPY|
                             NPY_ITER_ALLOCATE);
        /*
         * If buffering is enabled and copying is not,
         * clear the nbo_aligned flag and strip the data type
         * for the outer loops.
         */
        if ((flags&(NPY_ITER_BUFFERED)) &&
                !(op_flags[iiter]&(NPY_ITER_COPY|
                                   NPY_ITER_UPDATEIFCOPY|
                                   NPY_ITER_ALLOCATE))) {
            op_flags[iiter] &= ~NPY_ITER_NBO_ALIGNED;
            op_request_dtypes_inner[iiter] = op_request_dtypes[iiter];
            op_request_dtypes[iiter] = NULL;
        }
    }

    /* Only the inner loop gets the buffering and no inner flags */
    flags_inner = flags&~NPY_ITER_COMMON_DTYPE;
    flags &= ~(NPY_ITER_NO_INNER_ITERATION|
                    NPY_ITER_BUFFERED);

    for (inest = 0; inest < nnest; ++inest) {
        NewNpyArrayIterObject *iter;
        npy_intp *op_axes_niter[NPY_MAXARGS];

        /*
         * All the operands' op_axes are the same, except for
         * allocated outputs.
         */
        for (iiter = 0; iiter < niter; ++iiter) {
            if (op_flags[iiter]&NPY_ITER_ALLOCATE) {
                if (inest == 0) {
                    op_axes_niter[iiter] = NULL;
                }
                else {
                    op_axes_niter[iiter] = negones;
                }
            }
            else {
                op_axes_niter[iiter] = nested_op_axes[inest];
            }
        }

        /*
        printf("\n");
        for (iiter = 0; iiter < niter; ++iiter) {
            npy_intp i;

            for (i = 0; i < nested_naxes[inest]; ++i) {
                printf("%d ", (int)op_axes_niter[iiter][i]);
            }
            printf("\n");
        }
        */
        
        /* Allocate the iterator */
        iter = (NewNpyArrayIterObject *)npyiter_new(&NpyIter_Type, NULL, NULL);
        if (iter == NULL) {
            Py_DECREF(ret);
            goto fail;
        }

        if (inest < nnest-1) {
            iter->iter = NpyIter_MultiNew(niter, op, flags, order,
                                casting, op_flags, op_request_dtypes,
                                nested_naxes[inest], op_axes_niter,
                                0);
        }
        else {
            iter->iter = NpyIter_MultiNew(niter, op, flags_inner, order,
                                casting, op_flags_inner,
                                op_request_dtypes_inner,
                                nested_naxes[inest], op_axes_niter,
                                buffersize);
        }

        if (iter->iter == NULL) {
            Py_DECREF(ret);
            goto fail;
        }

        /* Cache some values for the member functions to use */
        npyiter_cache_values(iter);

        iter->started = 0;
        iter->finished = 0;

        /*
         * If there are any allocated outputs or any copies were made,
         * adjust op so that the other iterators use the same ones.
         */
        if (inest == 0) {
            PyArrayObject **objects = NpyIter_GetObjectArray(iter->iter);
            for (iiter = 0; iiter < niter; ++iiter) {
                if (op[iiter] != objects[iiter]) {
                    Py_XDECREF(op[iiter]);
                    op[iiter] = objects[iiter];
                    Py_INCREF(op[iiter]);
                }

                /*
                 * Clear any flags allowing copies for
                 * the rest of the iterators
                 */
                op_flags[iiter] &= ~(NPY_ITER_COPY|
                                 NPY_ITER_UPDATEIFCOPY);
            }
            /* Clear the common dtype flag for the rest of the iterators */
            flags &= ~NPY_ITER_COMMON_DTYPE;
        }

        PyTuple_SET_ITEM(ret, inest, (PyObject *)iter);
    }

    /* Release our references to the ops and dtypes */
    for (iiter = 0; iiter < niter; ++iiter) {
        Py_XDECREF(op[iiter]);
        Py_XDECREF(op_request_dtypes[iiter]);
        Py_XDECREF(op_request_dtypes_inner[iiter]);
    }

    /* Set up the nested child references */
    for (inest = 0; inest < nnest-1; ++inest) {
        NewNpyArrayIterObject *iter;
        iter = (NewNpyArrayIterObject *)PyTuple_GET_ITEM(ret, inest);
        /*
         * Indicates which iterator to reset with new base pointers
         * each iteration step.
         */
        iter->nested_child =
                (NewNpyArrayIterObject *)PyTuple_GET_ITEM(ret, inest+1);
        Py_INCREF(iter->nested_child);
        /*
         * Need to do a nested reset so all the iterators point
         * at the right data
         */
        NpyIter_ResetBasePointers(iter->nested_child->iter, iter->dataptrs);
    }

    return ret;

fail:
    for (iiter = 0; iiter < niter; ++iiter) {
        Py_XDECREF(op[iiter]);
        Py_XDECREF(op_request_dtypes[iiter]);
        Py_XDECREF(op_request_dtypes_inner[iiter]);
    }
    return NULL;
}

static void
npyiter_dealloc(NewNpyArrayIterObject *self)
{
    if (self->iter) {
        NpyIter_Deallocate(self->iter);
        self->iter = NULL;
        Py_XDECREF(self->nested_child);
        self->nested_child = NULL;
    }
    self->ob_type->tp_free((PyObject*)self);
}

static void
npyiter_resetbasepointers(NewNpyArrayIterObject *self)
{
    while (self->nested_child) {
        NpyIter_ResetBasePointers(self->nested_child->iter,
                                                    self->dataptrs);
        self = self->nested_child;
        self->started = 0;
        self->finished = 0;
    }
}

static PyObject *
npyiter_reset(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    NpyIter_Reset(self->iter);
    self->started = 0;
    self->finished = 0;

    /* If there is nesting, the nested iterators should be reset */
    npyiter_resetbasepointers(self);

    Py_RETURN_NONE;
}

static PyObject *
npyiter_iternext(NewNpyArrayIterObject *self)
{
    if (self->iter != NULL && !self->finished && self->iternext(self->iter)) {
        /* If there is nesting, the nested iterators should be reset */
        npyiter_resetbasepointers(self);

        Py_RETURN_TRUE;
    }
    else {
        self->finished = 1;
        Py_RETURN_FALSE;
    }
}

static PyObject *
npyiter_remove_coords(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    NpyIter_RemoveCoords(self->iter);
    /* RemoveCoords invalidates cached values */
    npyiter_cache_values(self);
    /* RemoveCoords also resets the iterator */
    self->started = 0;
    self->finished = 0;

    Py_RETURN_NONE;
}

static PyObject *
npyiter_remove_inner_loop(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    NpyIter_RemoveInnerLoop(self->iter);
    /* RemoveInnerLoop invalidates cached values */
    npyiter_cache_values(self);
    /* RemoveInnerLoop also resets the iterator */
    self->started = 0;
    self->finished = 0;

    Py_RETURN_NONE;
}

static PyObject *
npyiter_debug_print(NewNpyArrayIterObject *self)
{
    if (self->iter != NULL) {
        NpyIter_DebugPrint(self->iter);
    }
    else {
        printf("Iterator: (nil)\n");
    }

    Py_RETURN_NONE;
}

NPY_NO_EXPORT PyObject *
npyiter_seq_item(NewNpyArrayIterObject *self, Py_ssize_t i);

static PyObject *npyiter_value_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;

    npy_intp iiter, niter;
    PyArray_Descr **dtypes;
    char **dataptrs;

    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }

    niter = NpyIter_GetNIter(self->iter);
    dtypes = self->dtypes;
    dataptrs = self->dataptrs;

    /* Return an array  or tuple of arrays with the values */
    if (niter == 1) {
        ret = npyiter_seq_item(self, 0);
    }
    else {
        ret = PyTuple_New(niter);
        if (ret == NULL) {
            return NULL;
        }
        for (iiter = 0; iiter < niter; ++iiter) {
            PyTuple_SET_ITEM(ret, iiter, npyiter_seq_item(self, iiter));
        }
    }

    return ret;
}

static PyObject *npyiter_operands_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;

    npy_intp iiter, niter;
    PyArrayObject **objects;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    niter = NpyIter_GetNIter(self->iter);
    objects = self->objects;

    ret = PyTuple_New(niter);
    if (ret == NULL) {
        return NULL;
    }
    for (iiter = 0; iiter < niter; ++iiter) {
        PyObject *object = (PyObject *)objects[iiter];

        Py_INCREF(object);
        PyTuple_SET_ITEM(ret, iiter, object);
    }

    return ret;
}

static PyObject *npyiter_itviews_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;

    npy_intp iiter, niter;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    niter = NpyIter_GetNIter(self->iter);

    ret = PyTuple_New(niter);
    if (ret == NULL) {
        return NULL;
    }
    for (iiter = 0; iiter < niter; ++iiter) {
        PyArrayObject *view = NpyIter_GetIterView(self->iter, iiter);

        if (view == NULL) {
            Py_DECREF(ret);
            return NULL;
        }
        PyTuple_SET_ITEM(ret, iiter, (PyObject *)view);
    }

    return ret;
}

static PyObject *
npyiter_next(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL || self->finished) {
        return NULL;
    }

    /*
     * Use the started flag for the Python iteration protocol to work
     * when buffering is enabled.
     */
    if (self->started) {
        if (!self->iternext(self->iter)) {
            self->finished = 1;
            return NULL;
        }

        /* If there is nesting, the nested iterators should be reset */
        npyiter_resetbasepointers(self);
    }
    self->started = 1;

    return npyiter_value_get(self);
};

static PyObject *npyiter_shape_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;
    npy_intp idim, ndim, shape[NPY_MAXDIMS];

    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }

    if (NpyIter_GetShape(self->iter, shape) == NPY_SUCCEED) {
        ndim = NpyIter_GetNDim(self->iter);
        ret = PyTuple_New(ndim);
        if (ret != NULL) {
            for (idim = 0; idim < ndim; ++idim) {
                PyTuple_SET_ITEM(ret, idim,
                        PyInt_FromLong(shape[idim]));
            }
            return ret;
        }
    }

    return NULL;
}

static PyObject *npyiter_coords_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;
    npy_intp idim, ndim, coords[NPY_MAXDIMS];

    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }

    if (NpyIter_HasCoords(self->iter)) {
        ndim = NpyIter_GetNDim(self->iter);
        self->getcoords(self->iter, coords);
        ret = PyTuple_New(ndim);
        for (idim = 0; idim < ndim; ++idim) {
            PyTuple_SET_ITEM(ret, idim,
                    PyInt_FromLong(coords[idim]));
        }
        return ret;
    }
    else {
        PyErr_SetString(PyExc_ValueError,
                "Iterator does not have coordinates");
        return NULL;
    }
}

static int npyiter_coords_set(NewNpyArrayIterObject *self, PyObject *value)
{
    npy_intp idim, ndim, coords[NPY_MAXDIMS];

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return -1;
    }

    if (value == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Cannot delete coordinates");
        return -1;
    }

    if (NpyIter_HasCoords(self->iter)) {
        ndim = NpyIter_GetNDim(self->iter);
        if (!PySequence_Check(value)) {
            PyErr_SetString(PyExc_ValueError,
                    "Coordinates must be set with a sequence");
            return -1;
        }
        if (PySequence_Size(value) != ndim) {
            PyErr_SetString(PyExc_ValueError,
                    "Wrong number of coordinates");
            return -1;
        }
        for (idim = 0; idim < ndim; ++idim) {
            PyObject *v = PySequence_GetItem(value, idim);
            coords[idim] = PyInt_AsLong(v);
            if (coords[idim]==-1 && PyErr_Occurred()) {
                return -1;
            }
        }
        if (NpyIter_GotoCoords(self->iter, coords) != NPY_SUCCEED) {
            return -1;
        }
        self->started = 0;
        self->finished = 0;

        /* If there is nesting, the nested iterators should be reset */
        npyiter_resetbasepointers(self);

        return 0;
    }
    else {
        PyErr_SetString(PyExc_ValueError,
                "Iterator does not have coordinates");
        return -1;
    }
}

static PyObject *npyiter_index_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }

    if (NpyIter_HasIndex(self->iter)) {
        npy_intp index = *NpyIter_GetIndexPtr(self->iter);
        return PyInt_FromLong(index);
    }
    else {
        PyErr_SetString(PyExc_ValueError,
                "Iterator does not have an index");
        return NULL;
    }
}

static int npyiter_index_set(NewNpyArrayIterObject *self, PyObject *value)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return -1;
    }

    if (value == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Cannot delete index");
        return -1;
    }

    if (NpyIter_HasIndex(self->iter)) {
        npy_intp index;
        index = PyInt_AsLong(value);
        if (index==-1 && PyErr_Occurred()) {
            return -1;
        }
        if (NpyIter_GotoIndex(self->iter, index) != NPY_SUCCEED) {
            return -1;
        }
        self->started = 0;
        self->finished = 0;

        /* If there is nesting, the nested iterators should be reset */
        npyiter_resetbasepointers(self);

        return 0;
    }
    else {
        PyErr_SetString(PyExc_ValueError,
                "Iterator does not have an index");
        return -1;
    }
}

static PyObject *npyiter_iterindex_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }

    return PyInt_FromLong(NpyIter_GetIterIndex(self->iter));
}

static int npyiter_iterindex_set(NewNpyArrayIterObject *self, PyObject *value)
{
    npy_intp iterindex;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return -1;
    }

    if (value == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Cannot delete iterindex");
        return -1;
    }

    iterindex = PyInt_AsLong(value);
    if (iterindex==-1 && PyErr_Occurred()) {
        return -1;
    }
    if (NpyIter_GotoIterIndex(self->iter, iterindex) != NPY_SUCCEED) {
        return -1;
    }
    self->started = 0;
    self->finished = 0;

    /* If there is nesting, the nested iterators should be reset */
    npyiter_resetbasepointers(self);

    return 0;
}

static PyObject *npyiter_iterrange_get(NewNpyArrayIterObject *self)
{
    npy_intp istart = 0, iend = 0;
    PyObject *ret;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    NpyIter_GetIterIndexRange(self->iter, &istart, &iend);

    ret = PyTuple_New(2);
    if (ret == NULL) {
        return NULL;
    }

    PyTuple_SET_ITEM(ret, 0, PyInt_FromLong(istart));
    PyTuple_SET_ITEM(ret, 1, PyInt_FromLong(iend));

    return ret;
}

static int npyiter_iterrange_set(NewNpyArrayIterObject *self, PyObject *value)
{
    npy_intp istart = 0, iend = 0;
    PyObject *item;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return -1;
    }

    if (value == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Cannot delete iterrange");
        return -1;
    }

    if (!PyArg_ParseTuple(value, "nn", &istart, &iend)) {
        return -1;
    }

    if (NpyIter_ResetToIterIndexRange(self->iter, istart, iend)
                                                    != NPY_SUCCEED) {
        return -1;
    }
    if (istart < iend) {
        self->started = self->finished = 0;
    }
    else {
        self->started = self->finished = 1;
    }

    /* If there is nesting, the nested iterators should be reset */
    npyiter_resetbasepointers(self);

    return 0;
}

static PyObject *npyiter_hascoords_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    if (NpyIter_HasCoords(self->iter)) {
        Py_RETURN_TRUE;
    }
    else {
        Py_RETURN_FALSE;
    }
}

static PyObject *npyiter_hasindex_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    if (NpyIter_HasIndex(self->iter)) {
        Py_RETURN_TRUE;
    }
    else {
        Py_RETURN_FALSE;
    }
}

static PyObject *npyiter_dtypes_get(NewNpyArrayIterObject *self)
{
    PyObject *ret;

    npy_intp iiter, niter;
    PyArray_Descr **dtypes;

    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    niter = NpyIter_GetNIter(self->iter);

    ret = PyTuple_New(niter);
    if (ret == NULL) {
        return NULL;
    }
    dtypes = self->dtypes;
    for (iiter = 0; iiter < niter; ++iiter) {
        PyArray_Descr *dtype = dtypes[iiter];

        Py_INCREF(dtype);
        PyTuple_SET_ITEM(ret, iiter, (PyObject *)dtype);
    }

    return ret;
}

static PyObject *npyiter_ndim_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    return PyInt_FromLong(NpyIter_GetNDim(self->iter));
}

static PyObject *npyiter_niter_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    return PyInt_FromLong(NpyIter_GetNIter(self->iter));
}

static PyObject *npyiter_itersize_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is invalid");
        return NULL;
    }

    return PyInt_FromLong(NpyIter_GetIterSize(self->iter));
}

static PyObject *npyiter_finished_get(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL || !self->finished) {
        Py_RETURN_FALSE;
    }
    else {
        Py_RETURN_TRUE;
    }
}

NPY_NO_EXPORT Py_ssize_t
npyiter_seq_length(NewNpyArrayIterObject *self)
{
    if (self->iter == NULL) {
        return 0;
    }
    else {
        return NpyIter_GetNIter(self->iter);
    }
}

NPY_NO_EXPORT PyObject *
npyiter_seq_item(NewNpyArrayIterObject *self, Py_ssize_t i)
{
    PyObject *ret;

    npy_intp ret_ndim;
    npy_intp niter, innerloopsize, innerstride;
    char *dataptr;
    PyArray_Descr *dtype;

    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }
    niter = NpyIter_GetNIter(self->iter);
    if (i < 0 || i >= niter) {
        PyErr_Format(PyExc_IndexError,
                "Iterator operand index %d is out of bounds", (int)i);
        return NULL;
    }

#if 0
    /*
     * This check is disabled because it prevents things like
     * np.add(it[0], it[1], it[2]), where it[2] is a write-only
     * parameter.  When write-only, the value of it[i] is
     * likely random junk, as if it were allocated with an
     * np.empty(...) call.
     */
    if (!self->readflags[i]) {
        PyErr_Format(PyExc_RuntimeError,
                "Iterator operand %d is write-only", (int)i);
        return NULL;
    }
#endif

    dataptr = self->dataptrs[i];
    dtype = self->dtypes[i];

    if (NpyIter_HasInnerLoop(self->iter)) {
        innerloopsize = 1;
        innerstride = 0;
        /* If the iterator is going over every element, return array scalars */
        ret_ndim = 0;
    }
    else {
        innerloopsize = *self->innerloopsizeptr;
        innerstride = self->innerstrides[i];
        ret_ndim = 1;
    }

    Py_INCREF(dtype);
    ret = (PyObject *)PyArray_NewFromDescr(&PyArray_Type, dtype,
                            ret_ndim, &innerloopsize,
                            &innerstride, dataptr,
                            self->writeflags[i] ? NPY_WRITEABLE : 0, NULL);
    Py_INCREF(self);
    ((PyArrayObject *)ret)->base = (PyObject *)self;

    PyArray_UpdateFlags((PyArrayObject *)ret, NPY_UPDATE_ALL);

    return ret;
}

NPY_NO_EXPORT PyObject *
npyiter_seq_slice(NewNpyArrayIterObject *self,
                    Py_ssize_t ilow, Py_ssize_t ihigh)
{
    PyObject *ret;
    npy_intp niter;
    Py_ssize_t i;

    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return NULL;
    }
    niter = NpyIter_GetNIter(self->iter);
    if (ilow < 0) {
        ilow = 0;
    }
    else if (ilow >= niter) {
        ilow = niter-1;
    }
    if (ihigh < ilow) {
        ihigh = ilow;
    }
    else if (ihigh >= niter) {
        ihigh = niter-1;
    }

    ret = PyTuple_New(ihigh-ilow);
    if (ret == NULL) {
        return NULL;
    }
    for (i = ilow; i < ihigh ; ++i) {
        PyObject *item = npyiter_seq_item(self, i);
        if (item == NULL) {
            Py_DECREF(ret);
            return NULL;
        }
        PyTuple_SET_ITEM(ret, i-ilow, item);
    }
    return ret;
}

NPY_NO_EXPORT int
npyiter_seq_ass_item(NewNpyArrayIterObject *self, Py_ssize_t i, PyObject *v)
{

    npy_intp niter, innerloopsize, innerstride;
    char *dataptr;
    PyArray_Descr *dtype;
    PyArrayObject *tmp;
    int ret;

    if (v == NULL) {
        PyErr_SetString(PyExc_ValueError,
                        "can't delete iterator operands");
        return -1;
    }
    if (self->iter == NULL || self->finished) {
        PyErr_SetString(PyExc_ValueError,
                "Iterator is past the end");
        return -1;
    }
    niter = NpyIter_GetNIter(self->iter);
    if (i < 0 || i >= niter) {
        PyErr_Format(PyExc_IndexError,
                "Iterator operand index  %d is out of bounds", (int)i);
        return -1;
    }
    if (!self->writeflags[i]) {
        PyErr_Format(PyExc_RuntimeError,
                "Iterator operand %d is not writeable", (int)i);
        return -1;
    }

    dataptr = self->dataptrs[i];
    dtype = self->dtypes[i];

    if (NpyIter_HasInnerLoop(self->iter)) {
        innerloopsize = 1;
        innerstride = 0;
    }
    else {
        innerloopsize = *self->innerloopsizeptr;
        innerstride = self->innerstrides[i];
    }

    /* TODO - there should be a better way than this... */
    Py_INCREF(dtype);
    tmp = (PyArrayObject *)PyArray_NewFromDescr(&PyArray_Type, dtype,
                                1, &innerloopsize,
                                &innerstride, dataptr,
                                NPY_WRITEABLE, NULL);
    if (tmp == NULL) {
        return -1;
    }
    PyArray_UpdateFlags(tmp, NPY_UPDATE_ALL);
    ret = PyArray_CopyObject(tmp, v);
    Py_DECREF(tmp);
    return ret;
}

static PyMethodDef npyiter_methods[] = {
    {"reset", (PyCFunction)npyiter_reset, METH_NOARGS, NULL},
    {"iternext", (PyCFunction)npyiter_iternext, METH_NOARGS, NULL},
    {"remove_coords", (PyCFunction)npyiter_remove_coords, METH_NOARGS, NULL},
    {"remove_inner_loop", (PyCFunction)npyiter_remove_inner_loop,
                METH_NOARGS, NULL},
    {"debug_print", (PyCFunction)npyiter_debug_print, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL},
};

static PyMemberDef npyiter_members[] = {
    {NULL, 0, 0, 0, NULL},
};

static PyGetSetDef npyiter_getsets[] = {
    {"value",
        (getter)npyiter_value_get,
        NULL, NULL, NULL},
    {"shape",
        (getter)npyiter_shape_get,
        NULL, NULL, NULL},
    {"coords",
        (getter)npyiter_coords_get,
        (setter)npyiter_coords_set,
        NULL, NULL},
    {"index",
        (getter)npyiter_index_get,
        (setter)npyiter_index_set,
        NULL, NULL},
    {"iterindex",
        (getter)npyiter_iterindex_get,
        (setter)npyiter_iterindex_set,
        NULL, NULL},
    {"iterrange",
        (getter)npyiter_iterrange_get,
        (setter)npyiter_iterrange_set,
        NULL, NULL},
    {"operands",
        (getter)npyiter_operands_get,
        NULL, NULL, NULL},
    {"itviews",
        (getter)npyiter_itviews_get,
        NULL, NULL, NULL},
    {"hascoords",
        (getter)npyiter_hascoords_get,
        NULL, NULL, NULL},
    {"hasindex",
        (getter)npyiter_hasindex_get,
        NULL, NULL, NULL},
    {"dtypes",
        (getter)npyiter_dtypes_get,
        NULL, NULL, NULL},
    {"ndim",
        (getter)npyiter_ndim_get,
        NULL, NULL, NULL},
    {"niter",
        (getter)npyiter_niter_get,
        NULL, NULL, NULL},
    {"itersize",
        (getter)npyiter_itersize_get,
        NULL, NULL, NULL},
    {"finished",
        (getter)npyiter_finished_get,
        NULL, NULL, NULL},

    {NULL, NULL, NULL, NULL, NULL},
};

NPY_NO_EXPORT PySequenceMethods npyiter_as_sequence = {
#if PY_VERSION_HEX >= 0x02050000
    (lenfunc)npyiter_seq_length,            /*sq_length*/
    (binaryfunc)NULL,                       /*sq_concat*/
    (ssizeargfunc)NULL,                     /*sq_repeat*/
    (ssizeargfunc)npyiter_seq_item,         /*sq_item*/
    (ssizessizeargfunc)npyiter_seq_slice,   /*sq_slice*/
    (ssizeobjargproc)npyiter_seq_ass_item,  /*sq_ass_item*/
    (ssizessizeobjargproc)NULL,             /*sq_ass_slice*/
    (objobjproc)NULL,                       /*sq_contains */
    (binaryfunc)NULL,                       /*sq_inplace_concat */
    (ssizeargfunc)NULL,                     /*sq_inplace_repeat */
#else
    (inquiry)npyiter_seq_length,            /*sq_length*/
    (binaryfunc)NULL,                       /*sq_concat is handled by nb_add*/
    (intargfunc)NULL,                       /*sq_repeat is handled nb_multiply*/
    (intargfunc)npyiter_seq_item,           /*sq_item*/
    (intintargfunc)npyiter_seq_slice,       /*sq_slice*/
    (intobjargproc)npyiter_seq_ass_item,    /*sq_ass_item*/
    (intintobjargproc)NULL,                 /*sq_ass_slice*/
    (objobjproc)NULL,                       /*sq_contains */
    (binaryfunc)NULL,                       /*sg_inplace_concat */
    (intargfunc)NULL                        /*sg_inplace_repeat */
#endif
};

NPY_NO_EXPORT PyTypeObject NpyIter_Type = {
#if defined(NPY_PY3K)
    PyVarObject_HEAD_INIT(NULL, 0)
#else
    PyObject_HEAD_INIT(NULL)
    0,                                          /* ob_size */
#endif
    "numpy.newiter",                            /* tp_name */
    sizeof(NewNpyArrayIterObject),               /* tp_basicsize */
    0,                                          /* tp_itemsize */
    /* methods */
    (destructor)npyiter_dealloc,                /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
#if defined(NPY_PY3K)
    0,                                          /* tp_reserved */
#else
    0,                                          /* tp_compare */
#endif
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    &npyiter_as_sequence,                       /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    0,                                          /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,                         /* tp_flags */
    0,                                          /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    (iternextfunc)npyiter_next,                 /* tp_iternext */
    npyiter_methods,                            /* tp_methods */
    npyiter_members,                            /* tp_members */
    npyiter_getsets,                            /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    (initproc)npyiter_init,                     /* tp_init */
    0,                                          /* tp_alloc */
    npyiter_new,                                /* tp_new */
    0,                                          /* tp_free */
    0,                                          /* tp_is_gc */
    0,                                          /* tp_bases */
    0,                                          /* tp_mro */
    0,                                          /* tp_cache */
    0,                                          /* tp_subclasses */
    0,                                          /* tp_weaklist */
    0,                                          /* tp_del */
#if PY_VERSION_HEX >= 0x02060000
    0,                                          /* tp_version_tag */
#endif
};

