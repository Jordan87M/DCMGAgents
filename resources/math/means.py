def geomnaive(nums):
    ret = 1
    for num in nums:
        ret *= num
    return ret**(1/len(nums))
    