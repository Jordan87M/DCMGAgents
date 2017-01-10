class Group(object):
    def __init__(self,name,resources = [],membership = [], customers = [], **kwargs):
        self.name = name
        self.resources = resources
        self.membership = membership
        self.customers = customers
        
        self.security = -1
        
class Node(object):
    def __init__(self,name,resources = [], membership = [], customers = [], **kwargs):
        self.name = name 
        self.resources = resources