class customerProfile(object):
    def __init__(name,location,resources):
        self.name = name
        self.location = location
        self.resources = resources
    
        if type(loclist) is list:
            if loclist(0) == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist(0) == "AC":
                pass
        else:
            print("the first part of the location path should be AC or DC")
        
        self.customerAccount = Account(self.name,0.0)
        self.DRenrollee = False
    

class ResidentialCustomerProfile(customer):
    def __init__(self,name,location,**kwargs):
        super(ResidentialCustomerProfile,self).__init__(name,location,**kwargs)


class CommercialCustomerProfile(customer):
    def __init__(self,name,location,**kwargs):
        super(CommercialCustomerProfile,self).__init__(name,location,**kwargs)
        

class Account(object):
    def __init__(self,holder,initialBalance = 0):
        self.holder = holder
        self.accountBalance = initialBalance
        
    def adjustBalance(self,amount):
        self.accountBalance += amount
        if amount > 0:
            action = "credited"
        else:
            action = "debited"
        print("The account of {holder} has been {action} {amount} units".format(holder = self.holder, action = action, amount = amount))
        