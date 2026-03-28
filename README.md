# Optimizing waste recycling points in Eindhoven

**Advanced Simulation (2DI66) - Assignment 2**

This repository contains the source code, analysis and reporting for a simulation model for a waste recycling point, specifically the flow of customers through the facility, and the effective servicing dynamics of the system. 


## Problem statement

Simulate the intricate recycling waste drop-off system at Cure Milieustraat-Lodewijkstrat waste recycling point (WRP), so that the following can be determined: 

- Waiting times and queue lengths in the current state
- Evaluate the impact of having 20% more visitors to the WRP. 
- Suggest improvements that significantly improve the performance, these include: `shortening service times`, `adding parking spots`, `creating different stations`, `changing the routing`.


### Task and Requirements

Develop a discrete-event simulation, implement stochastic parameters based on data provided. 

### Description of Waste Recycling Plant

The WRP has two `routes` and 7 distinct `zones`.

#### WRP Zones

| Zone Name                            | Description                                                                                                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Entrance`                           | Where vehicles start queueing to enter the plant. A single-file line is formed here.                                                                           |
| `Hall`                               | Has it's own queue, `6-9 containers` (1-9), `12 single parking bays` which become `6 double vehicle bays`.                                                     |
| `Overflow`                           | `9 containers` (1-9) + `3 containers` (17-20) more = `total 12 containers`, `10 single parking bays` meaning small vehicles only.                                  |
| `Debris-clean & Debris-dirty (DcDd)` | `2 containers` (10-11), and `7 single parking bays` meaning maximum 3 big vehicles                                                                             |
| `Green`                              | Separate customer type, `5 single parking bays`                                                                                                                |
| `Rest` or `other`                    | Combines Asbestos and KCA with general waste recycling, has `5 containers` and  `5 single parking bays`, any customer type (`Type A` & `Type B`) can visit it. |
|                                      |                                                                                                                                                                |


#### WRP Routes
There are two routes connecting the zones, the routing of the zones are as follows:
  1. `Entrance` ⟶ `Green` ⟶ `Rest`
  2. `Entrance` ⟶ `Hall` ⟶ `Overflow` ⟶ `DcDd` ⟶ `Rest`. 

Given these routes please consider the assumptions for the flow of customers between zones `{ASSUMPTION_CODE}`, to understand
how a backlog develops between the zones. 


### Assumptions and Constraints

Constraints and Assumptions take one of two forms, this logical grouping exists, as it the nature, 
of the simulation changes based on these constraints, they are split up into:
`Ax` - assumption or constraint for simplicity, can be enforced through policy. 
`Rx` - assumption or constraint for realism.


| Code | Description                                                                                                                  |
| ---- | ---------------------------------------------------------------------------------------------------------------------------- |
| A1   | Only two types of vehicles `big` (vans or cars with small trailers), and `small` (cars) visit the plant.                     |
| A2   | A vehicle only brings one category of waste at a time, `Type A` - Green & `Type B` - General purpose                         |
| A3   | Since the `Hall` and `Overflow` have the 'similar' types of waste containers, a `Type B` vehicle will only visit one         |
| A4   | Call customers can go to `Rest` but not all will go; All type `Type B` customers can go to `DcDc` but not all will go.       |
| A5   | `Overflow` is never visited by `big` vehicles, instead they will always go to `Hall`.                                        |
| A6   | Operators (human or autonomous) direct vehicles to available `parking bays` on locations down stream on a `route`.           |
| A7   | Given `A5` Small vehicles prefer going to the `Overflow`, and will only visit the `Hall` if `Overflow` if full.              |
| A8   | A vehicle visiting multiple spots will only depart to the next spot when there is one available, thus preventing grid locks. |
| A9   | Tie breakers are carried out on a first come first serve basis.                                                              |
| A10  | All queues before zones are single file and are expressed in terms of the number of `Small` vehicles that can fit.           |
|      |                                                                                                                              |



  


| Code | Description                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------- |
| R1   | The `Hall` queue can fit at most `14 small vehicles`.                                                               |
| R2   | A vehicle blocked at the `Entrance`, blocks all vehicles behind it, the `Entrance` is a single vehicle choke point. |
| R3   | Both `Type A` and `Type B` customers may go to `Rest`, and `Type B`                                                 |
| R4   |                                                                                                                     |


## Implementation

To simulate this the following classes are implemented

Discrete Event Simulation: 

Events from the perspective of customer states

Scenario 1

- Customer Arrives at Plant (Creation Event)
- Customer Begins Waiting In Entrance Queue
- 
- Customer Begins Waiting For Entrance to clear, this means:
  1. The queue to Hall/Overflow is blocked 
  2. The service bays in Green are occupied. 

Type B: 
- Customer Begins Waiting in Hall/Overflow queue
- Customer Begins Service Hall/Overflow
- Customer Ends Service Hall/Overflow
- Customer Begins Waiting for DcDd
- Customer Begins Service DcDd
- Customer Ends Service DcDd
- Customer Begins Waiting for Rest
- Customer Begins Service Rest
- Customer Ends Service Rest
- Customer Leaves Plant

Type A: 
- Customer Begins Service at Green
- Customer Ends Service at Green
- Customer Begins Waiting for Rest
- Customer Begins Service Rest
- Customer Ends Service Rest
- Customer Leaves Plant


In  a queue:
Begin Waiting
Begin Waiting for downstream service to free

In a service
Begin Service -> End Service

End Service -> Begin Downstream activity
End Service -> Begin Waiting

After the final service of a customer we can assume that they Leave the plant

