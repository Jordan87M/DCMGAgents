class customerProfile(object):
    def __init__(name,location,**kwargs):
        self.name = name
        self.location = location
    
        if type(loclist) is list:
            if loclist(0) == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist(0) == "AC":
                pass
        else:
            print("the first part of the location path should be AC or DC")
    

class ResidentialCustomerProfile(customer):
    def __init__(self,name,location,**kwargs):
        super(ResidentialCustomerProfile,self).__init__(name,location,**kwargs)


class CommercialCustomerProfile(customer):
    pass

class Account(object):
    pass