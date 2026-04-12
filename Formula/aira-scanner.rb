class AiraScanner < Formula
  include Language::Python::Virtualenv

  desc "Static analysis for AI-generated code failure patterns"
  homepage "https://aira.bageltech.net"
  license "MIT"
  # Keep this tap head-only until the project publishes versioned release archives.
  head "https://github.com/BDB-Labs/aira-scanner.git", branch: "main"

  depends_on "python@3.13"

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz"
    sha256 "d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f"
  end

  def install
    venv = virtualenv_create(libexec, "python3.13")
    venv.pip_install resource("pyyaml")

    system libexec/"bin/python", "-m", "pip", "install",
           "--no-deps",
           "--no-build-isolation",
           buildpath/"CLI"

    bin.install_symlink libexec/"bin/aira"
  end

  test do
    (testpath/"sample.py").write <<~PYTHON
      try:
          risky()
      except Exception:
          pass
    PYTHON

    output = shell_output("#{bin}/aira scan #{testpath} --output json")
    assert_match "\"check_id\": \"C03\"", output
  end
end
