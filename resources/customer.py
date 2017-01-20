from DCMGClasses.CIP import tagClient

class CustomerProfile(object):
    def __init__(self,name,location,resources,**kwargs):
        self.name = name
        self.location = location
        self.resources = resources
        self.Resources = []
        
        loclist = self.location.split('.')
        if type(loclist) is list:
            if loclist[0] == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist[0] == "AC":
                pass
        else:
            print("the first part of the location path should be AC or DC")
        
        self.customerAccount = Account(self.name,0.0)
        self.DRenrollee = False
        
    #change maximum power draw for a customer
    def updateService(self,amount):
        self.maxDraw = amount
            
    def printInfo(self):
        print("    CUSTOMER: {name} is a {type}\n        LOCATION: {loc}\n        RESOURCES:".format(name = self.name, type = self.__class__.__name__, loc = self.location))
        for res in self.Resources:
            res.printInfo()
            
    def disconnectCustomer(self):
        signal = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_DUMMY".format(branch = self.branch, bus = self.bus, load = self.load)
        tagClient.writeTags([signal],[False])
        
    def measureVoltage(self):
        tag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measureCurrent(self):
        tag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measurePower(self):
        return self.measureVoltage()*self.measureCurrent()
                
        
class ResidentialCustomerProfile(CustomerProfile):
    def __init__(self,name,location,resources,**kwargs):
        super(ResidentialCustomerProfile,self).__init__(name,location,resources,**kwargs)
        self.maxDraw = 3
        self.rateAdjustment = 1
        
class CommercialCustomerProfile(CustomerProfile):
    def __init__(self,name,location,resources,**kwargs):
        super(CommercialCustomerProfile,self).__init__(name,location,resources,**kwargs)
        self.maxDraw = 6
        self.rateAdjustment = 1
        
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
        
        
class ResourceProfile(object):
    def __init__(self,owner,location,name,capCost,**kwargs):
        self.owner = owner
        self.capCost = capCost
        self.location = location
        self.name = name
            
    def setOwner(self,newOwner):
        self.owner = newOwner
        
    def printInfo(self):
        print("        RESOURCE: {name} is a {type}".format(name = self.name, type = self.__class__.__name__))
        print("            LOCATION: {loc}".format(loc = self.location))

class SourceProfile(ResourceProfile):
    def __init__(self,owner,location,name,capCost,maxDischargePower,**kwargs):
        super(SourceProfile,self).__init__(owner,location,name,capCost)
        self.maxDischargePower = maxDischargePower
        
class StorageProfile(SourceProfile):
    def __init__(self,owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,**kwargs):
        super(StorageProfile,self).__init__(owner,location,name,capCost,maxDischargePower,capacity)

class SolarProfile(SourceProfile):
    def __init__(self,owner,location,name,capCost,maxDischargePower,**kwargs):
        super(SolarProfile,self).__init__(owner,location,name,capCost,maxDischargePower,**kwargs)
        
class LeadAcidBatteryProfile(StorageProfile):
    def __init__(self,owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,**kwargs):
        super(LeadAcidBatteryProfile,self).__init__(owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,**kwargs)
        
        