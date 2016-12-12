def isRecipient(list,name):
    if type(list) is list:
        for item in list:
            if item == name:
                return True
        return False
    elif type(list) is str:
        if list == "broadcast" or list == "all":
            return True
        if list == name:
            return True
        else:
            return False