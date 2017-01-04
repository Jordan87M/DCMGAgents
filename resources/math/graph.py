
def findDisjointSubgraphs(matrix):
    dim = len(matrix)
    groups = []
    group = []
    expandlist = []
    unexamined = range(0,dim)
    while len(unexamined) > 0:
        group = []
        expandlist.append(unexamined[0])
        while len(expandlist) > 0:
            row = expandlist[0]
            for i in range(row,dim):
                if matrix[row][i] == 1 and row != i:
                    expandlist.append(i)
            unexamined.remove(row)
            expandlist.remove(row)
            group.append(row)
        groups.append(group)
            
    return groups
    
    
