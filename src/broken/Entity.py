
import numpy as np
from collections import deque

class Customer():

    def __init__(self, itinerary_gen):
        self.itinerary = itinerary_gen.Next()
        self.location = 0
        self.size = np.random.choice([1, 2], p=[0.53, 0.47])
        self.id = itinerary_gen.Count()

    def Destination(self):
        return self.itinerary[0]
    
    def MoveToDestination(self):
        self.location = self.itinerary.popleft()



class CustomerItineraryGenerator():

    BATCH_SIZE = 1000
    NUM_DESTINATIONS = 5
    NUM_STARTING_LOCATIONS = 5
    destinations = range(NUM_DESTINATIONS)

    def __init__(self):
        self.GenerateIteneraries()
        self.count = 0

    def GenerateIteneraries(self):
        self.itinerary_dq = deque()
        for _ in range(self.BATCH_SIZE):
            travel_matrix_list = self.CreateCustomerTravelMatrix()
            for travel_matrix in travel_matrix_list:
                curr_pos = 0
                itinerary = deque([curr_pos])
                destination = 0
                while destination < self.NUM_DESTINATIONS-1:
                    destination = np.random.choice(self.destinations, p=travel_matrix[curr_pos])
                    
                    curr_pos = destination+1
                    itinerary.append(curr_pos)

                self.itinerary_dq.append(itinerary)


    def Next(self):
        """
        return itinerary: list(int)
        0: Entrance
        1: Hall/Overflow
        2: Debris
        3: Green
        4: Rest
        5: Exit
        """
        self.count += 1
        if len(self.itinerary_dq)>0:
            return self.itinerary_dq.popleft()
        else:
            self.GenerateIteneraries()
            return self.itinerary_dq.popleft()
        

    def Count(self):
        return self.count

    def CreateCustomerTravelMatrix(self):
        """customer_type: str
        return: list()
        contains 0, 1 or 2 travel matrixes
        """
        travel_matrix_list = []


        customer_probabilities = np.array([12, 8, 7, 4, 22, 22, 3, 4, 1, 12, 5])/100
        assert sum(customer_probabilities) == 1
        customer_types = range(len(customer_probabilities))
        customer_type = np.random.choice(customer_types, p=customer_probabilities)


        main_tm = np.zeros((self.NUM_STARTING_LOCATIONS, self.NUM_DESTINATIONS))
        green_tm = np.zeros((self.NUM_STARTING_LOCATIONS, self.NUM_DESTINATIONS))
        green_tm[0][2] = 1 #Always straight to green

        if customer_type == 0:
            main_prob = 1
            green_prob = 0.31

            main_tm[0][0] = 1
            main_tm[1][1] = 0.13
        #-----------------------#

        if customer_type == 1:
            main_prob = 1
            green_prob = 0.316

            main_tm[0][0] = 1
            main_tm[1][1] = 0.26
            main_tm[1][3] = 0.1
        #-----------------------#

        if customer_type == 2:
            main_prob = 1
            green_prob = 0.2421

            main_tm[0][0] = 1
            main_tm[1][1] = 0.37
            main_tm[1][3] = 0.06
        #-----------------------#

        if customer_type == 3:
            main_prob = 1
            green_prob = 0.40

            main_tm[0][0] = 1
            main_tm[1][1] = 0.2
            main_tm[1][3] = 0.4
            main_tm[2][3] = 1

            green_tm[3][3] = 1
        #-----------------------#

        if customer_type == 4:
            main_prob = 0.63
            green_prob = 0.3844

            main_tm[0][1] = 0.25
            main_tm[0][3] = 0.75

            green_tm[3][3] = 0.03
        #-----------------------#

        if customer_type == 5:
            main_prob = 1
            green_prob = 0.2176

            main_tm[0][0] = 1
            main_tm[1][1] = 0.22
            main_tm[1][3] = 0.06
        #-----------------------#

        if customer_type == 6:
            main_prob = 1
            green_prob = 0

            main_tm[0][0] = 1
            main_tm[1][1] = 0.17
            main_tm[1][3] = 0.33
            main_tm[2][3] = 0.4
        #-----------------------#

        if customer_type == 7:
            main_prob = 1
            green_prob = 0.27

            main_tm[0][0] = 0.82
            main_tm[0][1] = 0.18
            main_tm[1][1] = 1
        #-----------------------#

        if customer_type == 8:
            main_prob = 1
            green_prob = 0

            main_tm[0][0] = 1
            main_tm[1][1] = 1
            main_tm[2][3] = 0.5
        #-----------------------#

        if customer_type == 9:
            main_prob = 1
            green_prob = 0.19

            main_tm[0][0] = 1
            main_tm[1][1] = 0.15
        #-----------------------#

        if customer_type == 10:
            main_prob = 0.15
            green_prob = 1

            main_tm[0][0] = 1

            green_tm[3][3] = 0.23
        #-----------------------#
        

        for row in main_tm:
            exit_prob = 1-sum(row)
            row[self.NUM_DESTINATIONS-1] = exit_prob

        for row in green_tm:
            exit_prob = 1-sum(row)
            row[self.NUM_DESTINATIONS-1] = exit_prob

        if main_prob > np.random.rand():
            travel_matrix_list.append(main_tm)

        if green_prob > np.random.rand():
            travel_matrix_list.append(green_tm)

        return travel_matrix_list

