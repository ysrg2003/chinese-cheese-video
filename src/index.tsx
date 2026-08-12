import { Composition, getInputProps, registerRoot } from "remotion";
import { XiangqiComposition } from "./Composition";
import { sampleJob } from "./sampleJob";
import type { VideoJob } from "./types";

const input = getInputProps() as Partial<VideoJob>;
const job: VideoJob = { ...sampleJob, ...input };

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="XiangqiComposition"
      component={XiangqiComposition}
      durationInFrames={Math.ceil(job.durationInSeconds * 30)}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={job}
    />
  );
};

registerRoot(RemotionRoot);
