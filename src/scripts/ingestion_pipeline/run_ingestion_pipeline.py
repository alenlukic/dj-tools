# noinspection PyUnresolvedReferences
import readline
import sys

from src.lib.ingestion_pipeline.track_ingestion_pipeline import *
from src.utils.errors import handle_error
from src.utils.assistant import print_error


def run_pipeline(step_args):
    """ Runs the track ingestion pipeline. """

    steps = {
        0: (InitialPipelineStage, TagRecordType.INITIAL.value),
        1: (PipelineStage, TagRecordType.POST_MIK.value),
        2: (PostRBPipelineStage, TagRecordType.POST_RB.value),
        3: (FinalPipelineStage, TagRecordType.FINAL.value)
    }
    to_run = set(steps.keys() if len(step_args) == 0 else step_args)

    n = 0
    print('Running ingestion pipeline. Type \'next\' to proceed to the next step.')
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
                    (step, arg) = steps[n]
                    step().execute() if arg is None else step(arg).execute()
                n += 1

            if n == NUM_STEPS:
                print('Pipeline ran successfully.')
                break
        except Exception as e:
            handle_error(e, 'An unexpected exception occurred:', print_error)
            break


if __name__ == '__main__':
    args = sys.argv
    run_pipeline([int(s) for s in args[1:]] if len(args) > 1 else [])
