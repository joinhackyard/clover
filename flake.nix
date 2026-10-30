{
  description = "Clover by Hackyard: macOS voice and AI assistant";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nixpkgs-darwin-legacy.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-darwin-legacy,
    }:
    let
      version = builtins.replaceStrings [ "\n" ] [ "" ] (builtins.readFile ./VERSION);
      targetSystems = [
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      forEachSystem =
        f:
        builtins.listToAttrs (
          map (system: {
            name = system;
            value = f system;
          }) targetSystems
        );
      pkgsFor =
        system:
        if system == "x86_64-darwin" then
          nixpkgs-darwin-legacy.legacyPackages.${system}
        else
          nixpkgs.legacyPackages.${system};
      packageFor =
        system:
        let
          pkgs = pkgsFor system;
        in
        pkgs.writeShellApplication {
          name = "clover";
          runtimeInputs = [ pkgs.python313 ];
          text = ''
            set -euo pipefail
            src=${./.}
            case "''${1:-}" in
              ""|install|--install|build|--build)
                exec bash "$src/build.sh"
                ;;
              --check)
                for f in clover.py clover_engine.py; do python3 -c 'import pathlib, sys; compile(pathlib.Path(sys.argv[1]).read_text(), sys.argv[1], "exec")' "$src/$f"; done
                bash -n "$src/build.sh"
                bash -n "$src/install.sh"
                printf '%s\n' 'clover source checks passed'
                ;;
              --version)
                printf '%s\n' "clover ${version}"
                ;;
              --help|-h|help)
                cat <<'EOF'
            Clover launcher for macOS.

            Usage:
              clover              Install or update Clover.app
              clover --install    Install or update Clover.app
              clover --check      Run packaged source checks
              clover --version    Print the packaged version
              clover --help       Show this help

            Building requires macOS 26 or later and Apple's command line tools.
            Full use also requires Claude Code, your own API key (Claude, OpenAI, Azure OpenAI or any endpoint), Devin, or Pi.
            EOF
                ;;
              *)
                printf 'Unknown option: %s\n\n' "$1" >&2
                exec "$0" --help
                ;;
            esac
          '';
          meta = with pkgs.lib; {
            description = "Clover by Hackyard: macOS app launcher";
            homepage = "https://github.com/joinhackyard/clover";
            license = licenses.mit;
            mainProgram = "clover";
            platforms = targetSystems;
          };
        };
    in
    {
      packages = forEachSystem (
        system:
        let
          clover = packageFor system;
        in
        {
          inherit clover;
          clover-mac = clover;
          source = clover;
          default = clover;
        }
      );

      apps = forEachSystem (
        system:
        let
          clover = self.packages.${system}.default;
          program = "${clover}/bin/clover";
          app = {
            type = "app";
            inherit program;
            inherit (clover) meta;
          };
        in
        {
          clover = app;
          clover-mac = app;
          default = app;
        }
      );

      checks = forEachSystem (system: {
        package = self.packages.${system}.default;
      });

      devShells = forEachSystem (system: {
        default =
          let
            pkgs = pkgsFor system;
          in
          pkgs.mkShell {
            packages = [
              pkgs.python313
              pkgs.act
            ];
            shellHook = ''
              echo "🍀 Clover development shell (Hackyard). Building the app requires Apple's command line tools."
            '';
          };
      });

      formatter = forEachSystem (system: (pkgsFor system).nixfmt);
    };
}
