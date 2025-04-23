{ pkgs ? import <nixpkgs> {} }:

let
  pythonWithPackages = pkgs.python3.withPackages (ps: [
    ps.numpy
    ps.textual
    # Custom ass package definition
    (ps.buildPythonPackage rec {
      pname = "ass";
      version = "0.5.2";
      src = ps.fetchPypi {
        inherit pname version;
        sha256 = "7mMe3ohw2K6n0BmXf9luyTTOi8d5zFZO/By91g5GKxc=";
      };
      propagatedBuildInputs = with ps; [ ];
    })
  ]);
in
pkgs.mkShell {
  buildInputs = with pkgs; [
    # Python with selected packages
    pythonWithPackages
    
    # System tools
    ffmpeg               # For ffprobe and video processing
    mkvtoolnix          # For mkvmerge
    
    # Development tools
    python3Packages.black   # Code formatter
    python3Packages.pylint  # Linter
    python3Packages.pytest  # Testing framework
  ];
  
  # Set up shell hook
  shellHook = ''
    # Display welcome message
    echo "Muxxy development environment activated!"
    echo "Available commands:"
    echo "  python main.py - Run the main application"
  '';
}