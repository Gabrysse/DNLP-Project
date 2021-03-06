import argparse
import nltk
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from scipy import stats
from tqdm import tqdm
import time
import os

from dataset.PolarityDataset import PolarityDataset
from dataset.Utilities import read_vader, read_glove, dataPreparation, getAmazonDF
from neural.net_softmax import NetSoftmax
from neural.train import train
from preprocessing import seed_regression, seed_filter, tok, get_token_counts, train_linear_model, seed_filter2

nltk.download('punkt')


def correlation_with_VADER(vader, seed, embeddings_index, net):
    if vader is None:
        vader = read_vader()

    polarities_vader = []
    polarities_seed = []
    polarities_net = []
    for token in vader.keys():
        polarities_vader.append(vader[token])

        try:
            polarities_seed.append(seed[token])
        except:
            polarities_seed.append(0)

        try:
            polarities_net.append(net(torch.tensor(embeddings_index[token]).unsqueeze(dim=0)).detach().item())
        except:
            polarities_net.append(0)

    polarities_vader = np.array(polarities_vader)
    polarities_seed = np.array(polarities_seed)
    polarities_net = np.array(polarities_net)

    # print(polarities_vader.shape)
    # print(polarities_seed.shape)
    # print(polarities_net.shape)

    print(f"Correlation SEED-VADER: {stats.pearsonr(polarities_vader, polarities_seed)[0]}")
    print(f"Correlation NETPREDICTION-VADER: {stats.pearsonr(polarities_vader, polarities_net)[0]}")


def unsupervised_review_sentiment(net, embeddings_index):
    paths = ["aclImdb/test/neg", "aclImdb/test/pos"]

    accuracy = 0
    tot = 0
    for i, path in enumerate(paths):
        print(f"Current path -> {path}")
        tot += len(os.listdir(path))
        for f in tqdm(os.listdir(path), position=0, leave=True):
            with open(os.path.join(path, f), 'r') as fp:
                review = fp.read()
            review_tok = tok(review)

            prediction = 0
            for word in review_tok:
                try:
                    prediction += net(torch.tensor(embeddings_index[word]).unsqueeze(dim=0)).detach().item()
                except:
                    pass

            prediction_score = prediction / len(review_tok)

            # print(prediction_score)

            if (i == 0 and prediction_score < 0) or (i == 1 and prediction_score > 0):
                accuracy += 1

    accuracy = accuracy / tot

    return accuracy


def main(args):
    vader = None
    embeddings_index = None

    # VALIDATION WITH VADER
    # vader = read_vader()
    # embeddings_index = read_glove()
    #
    # tokens, embeds, polarities, bucket = dataPreparation(vader, embeddings_index)
    #
    # train_tok, test_tok, train_emb, test_emb, train_pol, test_pol, train_bck, test_bck = train_test_split(tokens,
    #                                                                                                       embeds,
    #                                                                                                       polarities,
    #                                                                                                       bucket,
    #                                                                                                       test_size=0.2,
    #                                                                                                       stratify=bucket,
    #                                                                                                       shuffle=True)
    # train_tok, val_tok, train_emb, val_emb, train_pol, val_pol = train_test_split(train_tok, train_emb, train_pol,
    #                                                                               test_size=0.25, stratify=train_bck,
    #                                                                               shuffle=True)
    #
    # scale_max = np.max(polarities)
    # scale_min = np.min(polarities)
    #
    # glove_dataset = PolarityDataset(train_emb, train_pol)
    # glove_dataset_eval = PolarityDataset(val_emb, val_pol)
    # glove_dataset_test = PolarityDataset(test_emb, test_pol)
    #
    # train_dataloader = DataLoader(glove_dataset, batch_size=32, shuffle=True, num_workers=2, drop_last=True)
    # eval_dataloader = DataLoader(glove_dataset_eval, batch_size=1, shuffle=True, num_workers=2)
    # test_dataloader = DataLoader(glove_dataset_test, batch_size=1, shuffle=True, num_workers=2)
    #
    # net1 = NetSoftmax(scale_min, scale_max)
    # train(net1, train_dataloader, eval_dataloader)
    # checkpoint = {
    #     'scale_max': scale_max,
    #     'scale_min': scale_min,
    #     'model_state_dict': net1.state_dict()
    # }
    # torch.save(checkpoint, "net1.pth")
    #
    # # TEST
    # words = ["like", "love", "amazing", "excellent", "terrible", "awful", "ugly", "complaint"]
    #
    # net1.eval()
    #
    # for word in words:
    #     try:
    #         print("Predicted", word, net1(torch.tensor(embeddings_index[word]).unsqueeze(dim=0)).detach().item())
    #         print("Ground truth", word, vader[word])
    #     except:
    #         pass
    #     print("\n")
    #######################

    # VALIDATION WITH VADER
    print("\nDOMAIN SPECIFIC \n")

    df0 = getAmazonDF(args.dataset, args.filter_year)
    # vectorizer, regression = seed_regression(df0)
    # seed = seed_filter(df0, vectorizer, regression, frequency=500)

    X, features_list = get_token_counts(df0.reviewText)
    coeff = train_linear_model(X, df0.overall)
    seed = seed_filter2(X, features_list, coeff, frequency=500)

    print(f"Seed length: {len(seed)}")
    if embeddings_index is None:
        embeddings_index = read_glove()

    tokens, embeds, polarities, _ = dataPreparation(seed, embeddings_index)

    train_tok, test_tok, train_emb, test_emb, train_pol, test_pol = train_test_split(tokens, embeds, polarities,
                                                                                     test_size=0.2, shuffle=True)
    train_tok, val_tok, train_emb, val_emb, train_pol, val_pol = train_test_split(train_tok, train_emb, train_pol,
                                                                                  test_size=0.25, shuffle=True)

    scale_max = np.max(polarities)
    scale_min = np.min(polarities)

    glove_dataset = PolarityDataset(train_emb, train_pol)
    glove_dataset_eval = PolarityDataset(val_emb, val_pol)
    glove_dataset_test = PolarityDataset(test_emb, test_pol)

    train_dataloader = DataLoader(glove_dataset, batch_size=32, shuffle=True, num_workers=2, drop_last=True)
    eval_dataloader = DataLoader(glove_dataset_eval, batch_size=1, shuffle=True, num_workers=2)
    test_dataloader = DataLoader(glove_dataset_test, batch_size=1, shuffle=True, num_workers=2)

    net2 = NetSoftmax(scale_min, scale_max)
    train(net2, train_dataloader, eval_dataloader)
    checkpoint = {
        'scale_max': scale_max,
        'scale_min': scale_min,
        'model_state_dict': net2.state_dict()
    }
    torch.save(checkpoint, "net2.pth")

    correlation_with_VADER(vader, seed, embeddings_index, net2)
    #######################

    # print("\n Unsupervised Review Sentiment Classification")
    #
    # glove_vader_baseline = unsupervised_review_sentiment(net1, embeddings_index)
    # glove_seed_accuracy = unsupervised_review_sentiment(net1, embeddings_index)
    #
    # print(f"Glove-Vader BASELINE: {glove_vader_baseline}")
    # print(f"Glove-Seed ACCURACY: {glove_seed_accuracy}")


if __name__ == '__main__':
    # params = [
    #     '--num_epochs', '100',
    #     '--learning_rate', '2.5e-2',
    #     '--data', '../datasets/CamVid/',
    #     '--num_workers', '8',
    #     '--batch_size', '4',
    #     '--optimizer', 'sgd',
    #     '--checkpoint_step', '2'
    # ]
    # basic parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default="CamVid", help='Review dataset you are using.')
    parser.add_argument('--filter_year', action='store_true', help='Consider only the review < July 2014')

    parser.add_argument('--num_epochs', type=int, default=300, help='Number of epochs to train for')
    parser.add_argument('--epoch_start_i', type=int, default=0, help='Start counting epochs from this number')
    parser.add_argument('--checkpoint_step', type=int, default=100, help='How often to save checkpoints (epochs)')
    parser.add_argument('--validation_step', type=int, default=10, help='How often to perform validation (epochs)')
    parser.add_argument('--batch_size', type=int, default=1, help='Number of images in each batch')
    parser.add_argument('--learning_rate', type=float, default=0.01, help='learning rate used for train')
    parser.add_argument('--data', type=str, default='', help='path of training data')
    parser.add_argument('--num_workers', type=int, default=4, help='num of workers')
    parser.add_argument('--cuda', type=str, default='0', help='GPU ids used for training')
    parser.add_argument('--use_gpu', type=bool, default=True, help='whether to user gpu for training')
    parser.add_argument('--pretrained_model_path', type=str, default=None, help='path to pretrained model')
    parser.add_argument('--save_model_path', type=str, default=None, help='path to save model')
    parser.add_argument('--optimizer', type=str, default='rmsprop', help='optimizer, support rmsprop, sgd, adam')
    parser.add_argument('--loss', type=str, default='dice', help='loss function, dice or crossentropy')

    args = parser.parse_args()
    main(args)
