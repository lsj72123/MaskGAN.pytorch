# General Imports
from argparse import ArgumentParser
from tqdm import tqdm
from collections import namedtuple

# Torch imports
import torch
from torch.nn import functional as F
from torch import optim
from torch.utils.data import DataLoader


# FairSeq imports
from fairseq.meters import AverageMeter
from fairseq.progress_bar import tqdm_progress_bar

from mgan.preproc import Preprocess, mask, tokenize
from mgan.data import IMDbDataset, TensorIMDbDataset
# from mgan.models import MaskGAN
# from mgan.models import train, pretrain
from mgan.modules import build_trainer
from mgan.utils import Saver
from mgan.utils.debug_generate import debug_generate
from mgan.report_hooks import visdom

class Args: 
    criterion = 'dummy'

def dataset_test(args):
    # mask = {
    #     "type": "random",
    #     "kwargs": {"probability": 0.15}
    # }

    # mask = {
    #     "type": "end",
    #     "kwargs": {"n_chars": 2},
    # }

    # mask =  {
    #     "type": "contiguous_random",
    #     "kwargs": {"n_chars": 2},
    # }

    crmask = mask.ContiguousRandom(n_chars=2)
    spm_tokenize = tokenize.SentencePieceTokenizer(model_path=args.spm_path)
    max_tokens = 32000
    truncate = 10
    batch_size = max_tokens/truncate


    preprocess = Preprocess(mask=crmask, tokenize=spm_tokenize, truncate=truncate)
    dataset = TensorIMDbDataset(args.path, preprocess, rebuild=False)
    loader = DataLoader(dataset, batch_size=4096, 
            collate_fn=dataset.get_collate_fn(), 
            shuffle=True, num_workers=16)

    Task = namedtuple('Task', 'source_dictionary target_dictionary')
    task = Task(source_dictionary=dataset.vocab, 
            target_dictionary=dataset.vocab)

    meters = {}
    meters['epoch'] = AverageMeter()
    meters['loss'] = AverageMeter()

    device = torch.device('cuda')

    args = Args()
    max_epochs = 1000

    checkpoint_path = "/scratch/jerin/mgan/"
    saver = Saver(checkpoint_path)
    trainer = build_trainer("MLE", args, task)
    trainer = build_trainer("MGAN", args, task)

    saver.load_trainer(trainer)
    save_every = 20

    for epoch in tqdm(range(max_epochs), total=max_epochs, desc='epoch'):
        # new_loader = [next(iter(loader))]
        new_loader = loader
        pbar = tqdm_progress_bar(new_loader, epoch=epoch)
        meters["loss"].reset()
        count = 0
        for src, src_lens, src_mask, tgt, tgt_lens, tgt_mask in pbar:
            count += 1
            # src, tgt = src.to(device), tgt.to(device)
            # src_mask, tgt_mask = src_mask.to(device), tgt_mask.to(device)
            # src_lens, tgt_lens = src_lens.to(device), tgt_lens.to(device)
            summary = trainer.run(src, src_lens, src_mask, tgt, tgt_lens, tgt_mask)
            # visdom.log('generator-loss-vs-steps', 'line', summary['Generator Loss'])
            visdom.log('generator-loss-vs-steps', 
                    'line', summary['Generator Loss'])
            visdom.log('discriminator-real-loss-vs-steps', 
                    'line', summary['Discriminator Real Loss'])
            visdom.log('discriminator-fake-loss-vs-steps', 
                    'line', summary['Discriminator Fake Loss'])
            visdom.log('discriminator-overall-loss-vs-steps', 
                    'line', summary['Discriminator Overall Loss'])
            if count % (save_every) == 0:
                saver.checkpoint_trainer(trainer)


        avg_loss = meters["loss"].avg
        meters['epoch'].update(avg_loss)
        visdom.log('avg-generator-loss-vs-epoch', 'line', avg_loss)
        saver.checkpoint_trainer(trainer)
        #debug_generate(trainer.generator.model.model, loader, dataset.vocab, visdom)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--path', required=True)
    parser.add_argument('--spm_path', required=True)
    args = parser.parse_args()
    dataset_test(args)

