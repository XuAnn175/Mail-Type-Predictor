import torch
import torch.nn as nn
from sklearn.metrics import precision_recall_fscore_support
from torch.utils.data import Dataset
from transformers import AutoModel, AutoTokenizer

class MailDataset(Dataset):
    def __init__(self, df):
        super().__init__()
        self.data = {}
        for idx, row in df.iterrows():
            self.data[idx] = (row['msg_body'], row['label'])
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        msg_body, label = self.data[idx]
        return (msg_body, torch.tensor(label))


class BERT_IMDB(nn.Module):
    '''
    Fine-tuning DistillBert with two MLPs.
    '''
    def __init__(self, pretrained_type):
        super().__init__()

        num_labels = 2
        self.pretrained_model = AutoModel.from_pretrained(pretrained_type, num_labels=num_labels)
        
        self.classifier = nn.Sequential(
            nn.Linear(768, 512),
            nn.Dropout(0.1),
            nn.Linear(512, num_labels)
        )

    def forward(self, **pretrained_text):
        outputs = self.pretrained_model(**pretrained_text).last_hidden_state  # obtaining the last layer hidden states of the Transformer
        # the CLS token is in the beginning of the sequence. So, we grab its representation 
        # by indexing the tensor containing the hidden representations
        pretrained_output = outputs[:, 0, :]
        logits = self.classifier(pretrained_output)
        
        return logits


class BERT:
    def __init__(self, pretrained_type, config):
        self.config = config
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_type)
        self.model = BERT_IMDB(pretrained_type).to(config['device'])

    def train_label(self, train_dataloader, test_dataloader):
        device = self.config['device']
        ce_loss = nn.CrossEntropyLoss().to(device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config['lr'])

        for epoch in (range(self.config['epochs'])):
            # training stage
            self.model.train()
            for data in (train_dataloader):
                optimizer.zero_grad()
                text, label = list(data[0]), data[1].to(device)
                input_text = self.tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
                outputs = self.model(**input_text)

                loss = ce_loss(outputs, label)
                loss.backward()
                optimizer.step()
            # evaluating stage
            self.model.eval()
            pred = []
            labels = []
            for data in test_dataloader:
                text, label = list(data[0]), data[1].to(device)
                input_text = self.tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
                with torch.no_grad():
                    outputs = self.model(**input_text)
                pred.append(torch.argmax(outputs, dim=-1).cpu().numpy())
                labels.append(label.cpu().numpy())

            precision, recall, f1, support = precision_recall_fscore_support(labels, pred, average='macro', zero_division=1)
            precision = round(precision, 4)
            recall = round(recall, 4)
            f1 = round(f1, 4)
            print(f"Epoch: {epoch}, F1 score: {f1}, Precision: {precision}, Recall: {recall}")