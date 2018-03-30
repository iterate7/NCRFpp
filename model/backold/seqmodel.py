# -*- coding: utf-8 -*-
# @Author: Jie Yang
# @Date:   2017-10-17 16:47:32
# @Last Modified by:   Jie Yang,     Contact: jieynlp@gmail.com
# @Last Modified time: 2018-03-22 20:15:55

import torch
import torch.autograd as autograd
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from cnn import CNN
from bilstm import BiLSTM
from bigru import BiGRU
from crf import CRF

class SeqModel(nn.Module):
    def __init__(self, data):
        super(SeqModel, self).__init__()
        self.use_crf = data.use_crf
        print "build network..."
        print "word feature extractor: ", data.word_feature_extractor
        print "use crf: ", self.use_crf

        self.gpu = data.HP_gpu
        self.average_batch = data.HP_average_batch_loss
        ## add two more label for downlayer lstm, use original label size for CRF
        label_size = data.label_alphabet_size
        data.label_alphabet_size += 2
        if data.word_feature_extractor == "LSTM":
            self.word_hidden = BiLSTM(data)
        elif data.word_feature_extractor == "GRU":
            self.word_hidden = BiGRU(data)
        elif data.word_feature_extractor == "CNN":
            self.word_hidden = CNN(data)
        else:
            print "Illegal word feature extractor: ", data. word_feature_extractor
            exit(0)
        
        if self.use_crf:
            self.crf = CRF(label_size, self.gpu)


    def neg_log_likelihood_loss(self, word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover, batch_label, mask):
        outs = self.word_hidden.get_output_score(word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover)
        batch_size = word_inputs.size(0)
        seq_len = word_inputs.size(1)
        if self.use_crf:
            total_loss = self.crf.neg_log_likelihood_loss(outs, mask, batch_label)
            scores, tag_seq = self.crf._viterbi_decode(outs, mask)
        else:
            loss_function = nn.NLLLoss(ignore_index=0, size_average=False)
            outs = outs.view(batch_size * seq_len, -1)
            score = F.log_softmax(outs, 1)
            total_loss = loss_function(score, batch_label.view(batch_size * seq_len))
            _, tag_seq  = torch.max(score, 1)
            tag_seq = tag_seq.view(batch_size, seq_len)
        if self.average_batch:
            total_loss = total_loss / batch_size
        return total_loss, tag_seq




    def forward(self, word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover, mask):
        outs = self.word_hidden.get_output_score(word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover)
        batch_size = word_inputs.size(0)
        seq_len = word_inputs.size(1)
        if self.use_crf:
            scores, tag_seq = self.crf._viterbi_decode(outs, mask)
        else:
            outs = outs.view(batch_size * seq_len, -1)
            _, tag_seq  = torch.max(outs, 1)
            tag_seq = tag_seq.view(batch_size, seq_len)
            ## filter padded position with zero
            tag_seq = mask.long() * tag_seq
        return tag_seq


    def get_lstm_features(self, word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover):
        return self.word_hidden.get_lstm_features(word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover)


    def decode_nbest(self, word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover, mask, nbest):
        if not self.use_crf:
            print "Nbest output is currently supported only for CRF! Exit..."
            exit(0)
        outs = self.word_hidden.get_output_score(word_inputs, word_seq_lengths, char_inputs, char_seq_lengths, char_seq_recover)
        batch_size = word_inputs.size(0)
        seq_len = word_inputs.size(1)
        scores, tag_seq = self.crf._viterbi_decode_nbest(outs, mask, nbest)
        return scores, tag_seq

        