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
      width={String(job.format || "lesson").toLowerCase() === "short" ? 1080 : 1920}
      height={String(job.format || "lesson").toLowerCase() === "short" ? 1920 : 1080}
      defaultProps={job}
    />
  );
};

registerRoot(RemotionRoot);
