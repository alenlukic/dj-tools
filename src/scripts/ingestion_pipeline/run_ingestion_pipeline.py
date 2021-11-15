# noinspection PyUnresolvedReferences
import readline
import sys

from src.lib.ingestion_pipeline.track_ingestion_pipeline import *
from src.lib.error_management.service import handle
from src.utils.assistant import print_error


STEPS = {
        0: (InitialPipelineStage, TagRecordType.INITIAL.value),
        1: (PipelineStage, TagRecordType.POST_MIK.value),
        2: (PostRBPipelineStage, TagRecordType.POST_RB.value),
        3: (FinalPipelineStage, TagRecordType.FINAL.value)
    }


def run_pipeline(step_args):
    """ Runs the track ingestion pipeline. """

    print('Running ingestion pipeline. Type \'next\' to proceed to the next step.')

    n = 0
    to_run = set(STEPS.keys() if len(step_args) == 0 else step_args)
    while True:
        print('\n$ ', end='')
        try:
            cmd = input().lower()

            if cmd not in PIPELINE_CMDS:
                print('Type \'next\' to proceed to the next step or \'cancel\' to abort.')
                continue

            if cmd == 'cancel':
                print('Aborting.')
                break

            if cmd == 'next':
                if n in to_run:
                    (step, arg) = STEPS[n]
                    step().execute() if arg is None else step(arg).execute()
                else:
                    print('Skipping step %d' % n)

                n += 1

            if n == NUM_STEPS:
                print('Pipeline ran successfully.')
                break
        except Exception as e:
            handle(e, 'An unexpected exception occurred:', print_error)
            break


if __name__ == '__main__':
    args = sys.argv
    run_pipeline([int(s) for s in args[1:]] if len(args) > 1 else [])
