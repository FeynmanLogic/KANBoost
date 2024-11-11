from abc import ABC, abstractmethod
import torch
from kan import *

class MLPrefetchModel(object):
    '''
    Abstract base class for your models. For HW-based approaches such as the
    NextLineModel below, you can directly add your prediction code. For ML
    models, you may want to use it as a wrapper, but alternative approaches
    are fine so long as the behavior described below is respected.
    '''

    @abstractmethod
    def load(self, path):
        '''
        Loads your model from the filepath path
        '''
        pass

    @abstractmethod
    def save(self, path):
        '''
        Saves your model to the filepath path
        '''
        pass

    @abstractmethod
    def train(self, data):
        '''
        Train your model here. No return value. The data parameter is in the
        same format as the load traces. Namely,
        Unique Instr Id, Cycle Count, Load Address, Instruction Pointer of the Load, LLC hit/miss
        '''
        pass
        # for line in data:
        #     for instr_id, cycle,load_address, ip,llc_hit in line:
                #train model using monte carlo equations on Blocks under each page.


    @abstractmethod
    def generate(self, data):
        '''
        Generate your prefetches here. Remember to limit yourself to 2 prefetches
        for each instruction ID and to not look into the future :).

        The return format for this will be a list of tuples containing the
        unique instruction ID and the prefetch. For example,
        [
            (A, A1),
            (A, A2),
            (C, C1),
            ...
        ]

        where A, B, and C are the unique instruction IDs and A1, A2 and C1 are
        the prefetch addresses.
        '''
        pass

class KANBoostModel(MLPrefetchModel):
    def __init__(self):
        '''Initialize the KANBoost model parameters and settings.'''
        self.page_size = 36  
        self.block_size = 6
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = KAN(width=[5, 64, 128], grid=3, k=3, seed=0, device=self.device)

    def load(self, path):
        '''Loads model weights from a specified path.'''
        print(f'Loading model from {path}')
        self.model.load_state_dict(torch.load(path))

    def save(self, path):
        '''Saves model weights to a specified path.'''
        print(f'Saving model to {path}')
        torch.save(self.model.state_dict(), path)

    def ensure_48bit_address(self, load_address):
        return bin(int(load_address, 16))[2:].zfill(48)

    def calculate_delta(self, block1, block2):
        return int(block1, 2) - int(block2, 2)

    def preprocess_data(self, data):
        input_features, output_labels = [], []
        page_blocks = {}

        for i in range(len(data) - 1):
            instr_id, current_page, current_block, current_block_offset = self.split_load_address(data[i])
            _, next_page, next_block, _ = self.split_load_address(data[i + 1])

            # Initialize page_blocks if current_page is not present
            if current_page not in page_blocks:
                page_blocks[current_page] = ['000001']

            delta1 = delta2 = delta3 = 1

            if len(page_blocks[current_page]) > 1:
                delta1 = self.calculate_delta(page_blocks[current_page][-1], page_blocks[current_page][-2])
            if len(page_blocks[current_page]) > 2:
                delta2 = self.calculate_delta(page_blocks[current_page][-2], page_blocks[current_page][-3])
            if len(page_blocks[current_page]) > 3:
                delta3 = self.calculate_delta(page_blocks[current_page][-3], page_blocks[current_page][-4])

            next_delta = self.calculate_delta(next_block, current_block)
            input_features.append((instr_id, int(current_block, 2), delta1, delta2, delta3))
            output_labels.append(next_delta + 64)
            page_blocks[current_page].append(current_block)

        return input_features, output_labels

    def split_load_address(self, line):
        instr_id, cycle_count, load_address, instr_ptr, llc_hit_miss = line
        binary_address = self.ensure_48bit_address(load_address)
        page = binary_address[:self.page_size]
        block = binary_address[self.page_size:self.page_size + self.block_size]
        block_offset = binary_address[self.page_size + self.block_size:]
        return (instr_id, page, block, block_offset)

    def train(self, data):
        '''Trains the KANBoost model.'''
        print('Training KANBoostModel')
        input_features, output_labels = self.preprocess_data(data)
        data_tensor = torch.tensor(input_features, dtype=torch.float32, device=self.device)
        target_tensor = torch.tensor(output_labels, dtype=torch.long, device=self.device)
        train_data, test_data, train_target, test_target = train_test_split(data_tensor, target_tensor, test_size=0.2, random_state=42)
        
        traces_dataset = {
            'train_input': train_data,
            'test_input': test_data,
            'train_label': train_target,
            'test_label': test_target
        }

        # Training process
        def train_acc():
            return torch.mean((torch.argmax(self.model(traces_dataset['train_input']), dim=1) == traces_dataset['train_label']).float())

        def test_acc():
            return torch.mean((torch.argmax(self.model(traces_dataset['test_input']), dim=1) == traces_dataset['test_label']).float())

        results = self.model.fit(
            traces_dataset, opt="Adam", metrics=(train_acc, test_acc),
            loss_fn=torch.nn.CrossEntropyLoss(), steps=5000, lamb=0.01, lamb_entropy=10.05, save_fig=False
        )

    def generate(self, data):
        '''Generates prefetches using the KANBoost model predictions.'''
        print('Generating prefetches for KANBoostModel')
        prefetches = []
        input_features, _ = self.preprocess_data(data)
        data_tensor = torch.tensor(input_features, dtype=torch.float32, device=self.device)
        predictions = torch.argmax(self.model(data_tensor), dim=1)

        for instr_id, prediction in zip([d[0] for d in data], predictions):
            pf_addr = int(prediction.item())  # Prefetch based on predicted delta
            prefetches.append((instr_id, pf_addr))

        return prefetches


Model = KANBoostModel()


# class NextLineModel(MLPrefetchModel):

#     def load(self, path):
#         # Load your pytorch / tensorflow model from the given filepath
#         print('Loading ' + path + ' for NextLineModel')

#     def save(self, path):
#         # Save your model to a file
#         print('Saving ' + path + ' for NextLineModel')

#     def train(self, data):
#         '''
#         Train your model here using the data

#         The data is the same format given in the load traces. Namely:
#         Unique Instr Id, Cycle Count, Load Address, Instruction Pointer of the Load, LLC hit/miss
#         '''
#         print('Training NextLineModel')

#     def generate(self, data):
#         '''
#         Generate the prefetches for the prefetch file for ChampSim here

#         As a reminder, no looking ahead in the data and no more than 2
#         prefetches per unique instruction ID

#         The return format for this function is a list of (instr_id, pf_addr)
#         tuples as shown below
#         '''
#         print('Generating for NextLineModel')
#         prefetches = []
#         for (instr_id, cycle_count, load_addr, load_ip, llc_hit) in data:
#             # Prefetch the next two blocks
#             prefetches.append((instr_id, ((load_addr >> 6) + 1) << 6))
#             prefetches.append((instr_id, ((load_addr >> 6) + 2) << 6))

#         return prefetches

'''
# Example PyTorch Model
import torch
import torch.nn as nn

class PytorchMLModel(nn.Module):

    def __init__(self):
        super().__init__()
        # Initialize your neural network here
        # For example
        self.embedding = nn.Embedding(...)
        self.fc = nn.Linear(...)

    def forward(self, x):
        # Forward pass for your model here
        # For example
        return self.relu(self.fc(self.embedding(x)))

class TerribleMLModel(MLPrefetchModel):
    """
    This class effectively functions as a wrapper around the above custom
    pytorch nn.Module. You can approach this in another way so long as the the
    load/save/train/generate functions behave as described above.

    Disclaimer: It's terrible since the below criterion assumes a gold Y label
    for the prefetches, which we don't really have. In any case, the below
    structure more or less shows how one would use a ML framework with this
    script. Happy coding / researching! :)
    """

    def __init__(self):
        self.model = PytorchMLModel()
    
    def load(self, path):
        self.model = torch.load_state_dict(torch.load(path))

    def save(self, path):
        torch.save(self.model.state_dict(), path)

    def train(self, data):
        # Just standard run-time here
        self.model.train()
        criterion = nn.CrossEntropyLoss()
        optimizer = nn.optim.Adam(self.model.parameters())
        scheduler = nn.optim.lr_scheduler.StepLR(optimizer, step_size=0.1)
        for epoch in range(20):
            # Assuming batch(...) is a generator over the data
            for i, (x, y) in enumerate(batch(data)):
                y_pred = self.model(x)
                loss = criterion(y_pred, y)

                if i % 100 == 0:
                    print('Loss:', loss.item())

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            scheduler.step()

    def generate(self, data):
        self.model.eval()
        prefetches = []
        for i, (x, _) in enumerate(batch(data, random=False)):
            y_pred = self.model(x)
            
            for xi, yi in zip(x, y_pred):
                # Where instr_id is a function that extracts the unique instr_id
                prefetches.append((instr_id(xi), yi))

        return prefetches
'''

# Replace this if you create your own model
# Model = NextLineModel
