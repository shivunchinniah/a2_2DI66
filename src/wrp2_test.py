%load_ext autoreload
%autoreload 2

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from Entity import CustomerItineraryGenerator
from DSE import (
    Environment, LocationType, QueueLocation, 
    ServiceLocation, VehicleSize, Location, ItineraryItem
)

# Apply seaborn theme for clean visualizations
sns.set_theme(style="whitegrid")
class Sampler:
    def __init__(self, name, params, seed=None):
        self.rng = np.random.default_rng(seed)
        self._sampling_method = getattr(self.rng, name)
        self.dist_params = params

    def sample(self, size=None):
        val = self._sampling_method(**self.dist_params, size=size)
        return max(0.1, abs(float(np.squeeze(val))))

def get_gamma_params(mean, stdev):
    variance = stdev ** 2
    shape = (mean ** 2) / variance
    scale = variance / mean
    return {"shape": shape, "scale": scale}

# Data extracted from "Data Lodewijkstraat.xlsx"
samplers = {
    'entrance': Sampler('gamma', get_gamma_params(30, 12)),
    'hall_big': Sampler('gamma', get_gamma_params(423, 270)),
    'hall_small': Sampler('gamma', get_gamma_params(240, 150)),
    'overflow_small': Sampler('gamma', get_gamma_params(180, 150)),
    'dcdd': Sampler('gamma', get_gamma_params(331, 300)),
    'green': Sampler('gamma', get_gamma_params(341, 260)),
    'rest': Sampler('gamma', get_gamma_params(141, 36))
}
def generate_dse_customers(num_customers):
    generator = CustomerItineraryGenerator()
    dse_customers = []
    
    location_map = {
        0: LocationType.MAIN_QUEUE, 
        1: LocationType.HALL_OVERFLOW, 
        2: LocationType.DCDD, 
        3: LocationType.GREEN,
        4: LocationType.REST, 
        5: LocationType.EXIT
    }

    arrival_clock = 0.0

    for _ in range(num_customers):
        raw_itinerary = generator.Next()
        # Maintain the 47% big cars split from the excel document
        v_size = VehicleSize.BIG if np.random.rand() < 0.47 else VehicleSize.SMALL
        
        dse_itinerary = []
        for i, loc_int in enumerate(raw_itinerary):
            loc_enum = location_map[loc_int]
            
            # Dynamically sample service time using realistic distributions
            service_time = 0.0
            if loc_enum == LocationType.HALL_OVERFLOW:
                # The Excel notes differentiate Hall by Big/Small vehicle
                if v_size == VehicleSize.BIG:
                    service_time = samplers['hall_big'].sample()
                else:
                    # If it's a small car routed here, we sample 'hall_small'
                    service_time = samplers['hall_small'].sample()
            elif loc_enum == LocationType.DCDD:
                service_time = samplers['dcdd'].sample()
            elif loc_enum == LocationType.GREEN:
                service_time = samplers['green'].sample()
            elif loc_enum == LocationType.REST:
                service_time = samplers['rest'].sample()
                
            item = ItineraryItem(location=loc_enum, service_time=service_time)
            
            if i == 0:
                item.start_time = arrival_clock
                
            dse_itinerary.append(item)
            
            # Inject the physical HALL_QUEUE right after MAIN_QUEUE
            if i == 0:
                dse_itinerary.append(ItineraryItem(location=LocationType.HALL_QUEUE, service_time=0))
                
        import DSE 
        dse_customers.append(DSE.Customer(dse_itinerary, v_size))
        
        # Space out arrivals according to the Entrance distribution (mean 30, stdev 12)
        arrival_clock += samplers['entrance'].sample()
        
    return dse_customers
def setup_environment(customers):
    # 1. Instantiate Locations
    entrance = QueueLocation(LocationType.MAIN_QUEUE, maximum_capacity=99999)
    hall_queue = QueueLocation(LocationType.HALL_QUEUE, maximum_capacity=14)
    
    hall_pairs = [[i, i+1] for i in range(0, 12, 2)]
    hall_overflow = ServiceLocation(LocationType.HALL_OVERFLOW, max_capacity=12, single_bays=22, single_bay_pairs=hall_pairs)
    
    dcdd_pairs = [[0, 1], [2, 3], [4, 5]]
    dcdd = ServiceLocation(LocationType.DCDD, max_capacity=7, single_bays=7, single_bay_pairs=dcdd_pairs)
    
    green_pairs = [[0, 1], [1, 2], [2, 3], [3, 4]]
    green = ServiceLocation(LocationType.GREEN, max_capacity=5, single_bays=5, single_bay_pairs=green_pairs)
    
    rest_pairs = [[0, 1], [1, 2], [2, 3], [3, 4]]
    rest = ServiceLocation(LocationType.REST, max_capacity=5, single_bays=5, single_bay_pairs=rest_pairs)
    
    exit_node = QueueLocation(LocationType.EXIT, maximum_capacity=999999)

    # 2. Connect Routing
    entrance.connect(hall_queue)
    hall_queue.connect(hall_overflow)
    hall_queue.connect(dcdd)
    hall_queue.connect(green)
    hall_queue.connect(rest)
    hall_queue.connect(exit_node)

    dcdd.connect(rest)
    green.connect(rest)
    hall_overflow.connect(rest)
    
    hall_overflow.connect(dcdd)
    
    hall_overflow.connect(exit_node)
    dcdd.connect(exit_node)
    green.connect(exit_node)
    rest.connect(exit_node)

    locations_dict = {
        LocationType.MAIN_QUEUE: entrance,
        LocationType.HALL_QUEUE: hall_queue,
        LocationType.HALL_OVERFLOW: hall_overflow,
        LocationType.DCDD: dcdd,
        LocationType.GREEN: green,
        LocationType.REST: rest,
        LocationType.EXIT: exit_node
    }
    
    return Environment(customers, locations_dict, initial_time=0)
def run_replications(num_customers, num_replications=30):
    all_traces = []
    all_turnarounds = []
    
    for rep in range(num_replications):
        # Generate fresh independent distributions and environments
        customers = generate_dse_customers(num_customers)
        env = setup_environment(customers)
        
        # Run up to 35000s (~9.7 hours) to ensure all customers finish
        env.run(end_time=35000)
        
        # Extract traces for plot logs
        data = []
        for i, c in enumerate(customers):
            cid = getattr(c, 'id', i) 
            for item in c.itinerary:
                data.append({
                    'replication': rep,
                    'customer_id': cid,
                    'vehicle_size': c.vehicle_size.name,
                    'location': item.location.name,
                    'start_time': item.start_time,
                    'end_time': item.end_time,
                    'wait_time': item.time_waiting,
                    'service_time': item.service_time
                })
                
        df_rep = pd.DataFrame(data)
        df_rep['queue_exit_time'] = df_rep['start_time'] + df_rep['wait_time']
        all_traces.append(df_rep)
        
        # Extract specific turnaround metrics
        sys_time = df_rep.groupby('customer_id').agg(
            entry_time=('start_time', 'min'),
            exit_time=('end_time', 'max')
        )
        sys_time['total_time'] = sys_time['exit_time'] - sys_time['entry_time']
        sys_time['replication'] = rep
        all_turnarounds.append(sys_time)
        
    return pd.concat(all_traces, ignore_index=True), pd.concat(all_turnarounds, ignore_index=True)

print("Running 30 Monte Carlo Replications for Baseline (605 Cars)...")
df_base, turn_base = run_replications(num_customers=605, num_replications=30)
print("Finished Baseline.")
print("\nRunning 30 Monte Carlo Replications for +20% Scenario (726 Cars)...")
df_inc, turn_inc = run_replications(num_customers=726, num_replications=30)
print("Finished +20% Scenario.")
def plot_statistical_wait_times(df, title):
    df_filtered = df[df['location'] != 'EXIT'].copy()
    df_filtered['Wait Type'] = df_filtered['service_time'].apply(
        lambda x: 'Waiting in Queue' if x == 0 else 'Blocked (Downstream Full)'
    )
    
    plt.figure(figsize=(12, 7))
    sns.barplot(
        data=df_filtered, 
        x='location', 
        y='wait_time', 
        hue='Wait Type', 
        dodge=False, 
        palette='magma',
        errorbar=('ci', 95)  # Let seaborn compute explicit 95% Confidence Intervals bootstrapped across executions!
    )
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylabel('Average Wait/Blocked Time (seconds)', fontsize=12)
    plt.xlabel('Location', fontsize=12)
    plt.xticks(rotation=45)
    plt.legend(title='Bottleneck Reason', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()

plot_statistical_wait_times(df_base, 'Baseline: Statistical Mean Wait & Blocked Time By Node (95% CI)')
plot_statistical_wait_times(df_inc, '+20% Scenario: Statistical Mean Wait & Blocked Time By Node (95% CI)')
def plot_turnaround_times_kde(turn_base, turn_inc):
    plt.figure(figsize=(12, 7))
    
    turn_base['Scenario'] = 'Baseline (605 cars)'
    turn_inc['Scenario'] = '+20% (726 cars)'
    
    combined = pd.concat([turn_base, turn_inc])
    
    sns.kdeplot(data=combined, x='total_time', hue='Scenario', fill=True, common_norm=False, palette='crest', alpha=0.5)
    
    plt.title("Turnaround Time Density (Aggregated across 30 Replications)", fontsize=14, fontweight='bold')
    plt.xlabel('Total Time spent in system (seconds)', fontsize=12)
    plt.ylabel('Density', fontsize=12)
    plt.tight_layout()
    plt.show()
    
    print(f"Baseline Grand Mean Turnaround: {turn_base['total_time'].mean():.2f} +/- {turn_base['total_time'].sem() * 1.96:.2f} seconds")
    print(f"+20% Grand Mean Turnaround:     {turn_inc['total_time'].mean():.2f} +/- {turn_inc['total_time'].sem() * 1.96:.2f} seconds")

plot_turnaround_times_kde(turn_base, turn_inc)
def plot_queue_progress_ci(df, title):
    """
    Calculates and plots the true queue size at 60 second intervals 
    over the entire simulation duration, aggregating across replications to form CI bands.
    """
    # Sample queue lengths at 60 second intervals
    time_bins = np.arange(0, 35000, 60)
    locations = [loc for loc in df['location'].unique() if loc != 'EXIT']
    
    # Extract arrays effectively
    records = []
    
    for rep in df['replication'].unique():
        rep_df = df[df['replication'] == rep]
        for loc in locations:
            loc_df = rep_df[(rep_df['location'] == loc) & (rep_df['start_time'] < rep_df['end_time'])]
            if loc_df.empty: continue
            
            arrivals = pd.DataFrame({'time': loc_df['start_time'], 'change': 1})
            departures = pd.DataFrame({'time': loc_df['end_time'], 'change': -1})
            events = pd.concat([arrivals, departures]).sort_values(by=['time', 'change'], ascending=[True, False])
            events['occupancy'] = events['change'].cumsum()
            
            # Search sorted rapidly calculates the nearest relevant time event index for our 60 second intervals
            idxs = np.searchsorted(events['time'].values, time_bins, side='right') - 1
            occupancies = np.where(idxs >= 0, events['occupancy'].values[idxs], 0)
            
            # Append multiple rows to the dataframe directly instead of row by row (massive performance boost)
            temp_df = pd.DataFrame({'time': time_bins, 'occupancy': occupancies})
            temp_df['location'] = loc
            temp_df['replication'] = rep
            records.append(temp_df)
            
    progress_df = pd.concat(records, ignore_index=True)
    
    plt.figure(figsize=(14, 7))
    
    # We use ci=95 effectively here to draw error bounds
    sns.lineplot(data=progress_df, x='time', y='occupancy', hue='location', errorbar=('ci', 95), linewidth=2)
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel('Simulation Time (seconds)', fontsize=12)
    plt.ylabel('Average Occupancy in Replications (Vehicles)', fontsize=12)
    plt.legend(title='Location', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()

print("Building Line plots (this takes a few seconds)...")
plot_queue_progress_ci(df_base, 'Baseline: Queue Size Progress Over Time (With 95% Confidence Interval Bands)')
plot_queue_progress_ci(df_inc, '+20% Scenario: Queue Size Progress Over Time (With 95% Confidence Interval Bands)')
