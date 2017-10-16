"""Training and validation code for bddmodelcar."""
import sys
import traceback
import logging
import time

from Parameters import ARGS
from Dataset import Dataset

import Utils

import matplotlib.pyplot as plt

from nets.SqueezeNetTimeLSTM import SqueezeNetTimeLSTM
from torch.autograd import Variable
import torch.nn.utils as nnutils
import torch


def main():
    logging.basicConfig(filename='training.log', level=logging.DEBUG)
    logging.debug(ARGS)  # Log arguments

    # Set Up PyTorch Environment
    # torch.set_default_tensor_type('torch.FloatTensor')
    torch.cuda.set_device(ARGS.gpu)
    torch.cuda.device(ARGS.gpu)

    net = SqueezeNetTimeLSTM().cuda()
    criterion = torch.nn.MSELoss().cuda()
    optimizer = torch.optim.Adadelta(net.parameters())

    try:
        epoch = ARGS.epoch

        if not epoch == 0:
            import os
            print("Resuming")
            save_data = torch.load(os.path.join(ARGS.save_path, "epoch%02d.weights" % (epoch - 1,)))
            net.load_state_dict(save_data)

        logging.debug('Starting training epoch #{}'.format(epoch))

        net.train()  # Train mode

        train_dataset = Dataset('/hostroot/home/ehou/trainingAll/training/data/train/', [], ARGS.ignore, seed=123123123,
                                nframes=6, train_ratio=1., mini_epoch_ratio=0.1)
        train_data_loader = train_dataset.get_train_loader(batch_size=150, shuffle=True, pin_memory=False)

        train_loss = Utils.LossLog()
        start = time.time()
        for batch_idx, (camera, meta, truth, mask) in enumerate(train_data_loader):
            # Cuda everything
            camera = camera.cuda()
            meta = meta.cuda()
            truth = truth.cuda()
            mask = mask.cuda()
            truth = truth * mask

            # Forward
            optimizer.zero_grad()
            outputs = net(Variable(camera), Variable(meta)).cuda()
            mask = Variable(mask)

            outputs = outputs * mask

            loss = criterion(outputs, Variable(truth))

            # Backpropagate
            loss.backward()
            nnutils.clip_grad_norm(net.parameters(), 1.0)
            optimizer.step()

            # Logging Loss
            train_loss.add(loss.data[0])

            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(camera), len(train_data_loader.dataset.train_part),
                100. * batch_idx / len(train_data_loader), loss.data[0]))

            cur = time.time()
            print('{} Hz'.format(150./(cur - start)))
            start = cur


        Utils.csvwrite('trainloss.csv', [train_loss.average()])

        logging.debug('Finished training epoch #{}'.format(epoch))
        logging.debug('Starting validation epoch #{}'.format(epoch))

        val_dataset = Dataset('/hostroot/home/ehou/trainingAll/training/data/val/', [], ARGS.ignore, seed=123123123,
                                nframes=6, train_ratio=0.8)
        val_data_loader = val_dataset.get_val_loader(batch_size=150, shuffle=True, pin_memory=False)

        val_loss = Utils.LossLog()

        net.eval()

        for batch_idx, (camera, meta, truth, mask) in enumerate(val_data_loader):
            # Cuda everything
            camera = camera.cuda()
            meta = meta.cuda()
            truth = truth.cuda()
            mask = mask.cuda()
            truth = truth * mask

            # Forward
            outputs = net(Variable(camera), Variable(meta)).cuda()
            mask = Variable(mask)

            outputs = outputs * mask

            loss = criterion(outputs, Variable(truth))

            # Logging Loss
            val_loss.add(loss.cpu().data[0])

	    print('Val Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
		epoch, batch_idx * len(camera), len(val_data_loader.dataset.val_part),
		100. * batch_idx / len(val_data_loader), loss.data[0]))

        Utils.csvwrite('valloss.csv', [val_loss.average()])

        logging.debug('Finished validation epoch #{}'.format(epoch))
        Utils.save_net("epoch%02d" % (epoch,), net)

    except Exception:
        logging.error(traceback.format_exc())  # Log exception
        sys.exit(1)

if __name__ == '__main__':
    main()