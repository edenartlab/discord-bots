const WORKDIR = "/marsbots";

module.exports = {
  apps: [
    {
      name: "abraham",
      script: `${WORKDIR}/bot.py`,
      interpreter: "python",
      args: `${WORKDIR}/bots/abraham/abraham.json --cog-path=bots.abraham.abraham --dotenv-path=${WORKDIR}/bots/abraham/.env`,
      watch: [`${WORKDIR}/bots/abraham`],
      ignore_watch: ["__pycache__", "*.pyc"],
      watch_delay: 1000,
    },
  ],
};
