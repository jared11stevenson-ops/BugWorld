import json,sys
def gen(steal=1, target=12, rv=3):
    O=lambda a:["==",["act","opp"],a]
    return {"id":"rt_seat","name":"Raid Seat Bias","vars":[["pts",0,0,30]],
    "actions":[
    {"name":"bank","cond":0,"fx":[["+=","me","pts",2]]},
    {"name":"raid","cond":0,"fx":[["+=","me","pts",["?",O(0),rv,0]],["=","opp","pts",["-",["v","opp","pts"],steal]]]},
    {"name":"guard","cond":0,"fx":[["+=","me","pts",["?",O(1),4,1]]]}],
    "passive":[],"end":[[[">=",["v","me","pts"],target],1]],"tiebreak":"pts","max_rounds":25,"value":[["pts",1]]}
if __name__=="__main__":
    json.dump(gen(*map(int,sys.argv[1:4])),open(sys.argv[4],"w"))
