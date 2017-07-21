from copy import copy

class MultiDimArray(object):
    def __init__(dimensions,value=0):
        mat = value
        for dim in reversed(dimensions):
            mat1 = copy(mat)
            mat = []
            for x in range(dim):
                mat.append(mat1)
        return mat
    
    def iteratearray(array,function):
        dims = []
        indices = []
        
        #determine array dimensionality and size
        arr = array
        while type(arr) is list:
            arr = array[0]
            dims.append(len(arr))
            indices.append(0)
        ndim = len(dims)
            
        while indices[0] < dims[0]:
            indices[-1] += 1
            indexindex = 1
            while indices[-indexindex] >= dimensions[-indexindex]:
                indices[-indexindex] = 0
                indexindex += 1
                indices[-indexindex] += 1
                
                if indexindex > ndim:
                    print("indexindex > ndim")
                    break
            
            function(indices)
            
            