const paths = ['src/', 'tests/', 'deploy/', 'pyproject.toml', 'uv.lock', '.python-version',
  '.dockerignore', '.github/workflows/deploy-development.yml'];

// Permit newer documentation-only commits, but never deploy superseded application code.
module.exports = async ({ github, context, branch = 'development' }) => {
  const relevant = name => typeof name === 'string' && paths.some(path =>
    path.endsWith('/') ? name.startsWith(path) : name === path);
  const { data: ref } = await github.rest.git.getRef({
    ...context.repo, ref: `heads/${branch}`,
  });
  if (ref.object.sha === context.sha) return true;
  const pageSize = 100;
  const { data: comparison } = await github.rest.repos.compareCommitsWithBasehead({
    ...context.repo, basehead: `${context.sha}...${ref.object.sha}`, per_page: pageSize, page: 1,
  });
  // A full first page may hide relevant files on page 2, so only a partially-filled page
  // is evidence we can act on; anything else (diverged, missing, oversized) declines.
  if (comparison.status !== 'ahead' || !Array.isArray(comparison.files)
    || comparison.files.length === 0 || comparison.files.length >= pageSize) return false;
  return comparison.files.every(file => !relevant(file.filename) && !relevant(file.previous_filename));
};
