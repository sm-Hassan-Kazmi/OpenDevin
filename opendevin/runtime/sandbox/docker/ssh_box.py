import sys
import time
import uuid

import docker

from opendevin.core.config import config
from opendevin.core.const.guide_url import TROUBLESHOOTING_URL
from opendevin.core.exceptions import SandboxInvalidBackgroundCommandError
from opendevin.core.logger import opendevin_logger as logger
from opendevin.runtime.plugins import AgentSkillsRequirement, JupyterRequirement
from opendevin.runtime.sandbox.docker.process import DockerProcess, Process
from opendevin.runtime.sandbox.ssh import SSHBox
from opendevin.runtime.utils import find_available_tcp_port


class DockerSSHBox(SSHBox):
    instance_id: str
    container_image: str
    container_name_prefix = 'opendevin-sandbox-'
    container_name: str
    container: docker.models.containers.Container
    docker_client: docker.DockerClient

    def __init__(
        self,
        container_image: str | None = None,
        timeout: int = config.sandbox_timeout,
        sid: str | None = None,
    ):
        # Initialize docker client. Throws an exception if Docker is not reachable.
        try:
            self.docker_client = docker.from_env()
        except Exception as ex:
            logger.exception(
                f'Error creating controller. Please check Docker is running and visit `{TROUBLESHOOTING_URL}` for more debugging information.',
                exc_info=False,
            )
            raise ex

        if config.persist_sandbox:
            self.instance_id = 'persisted'
        else:
            self.instance_id = (sid or '') + str(uuid.uuid4())

        self.timeout = timeout
        self.container_image = container_image or config.sandbox_container_image
        self.container_name = self.container_name_prefix + self.instance_id

        self._username = config.ssh_username
        if config.persist_sandbox:
            if not config.ssh_password:
                raise Exception(
                    'Please add ssh_password to your config.toml or add -e SSH_PASSWORD to your docker run command'
                )
            self._password = config.ssh_password
            self._port = config.ssh_port
        else:
            self._password = str(uuid.uuid4())
            self._port = find_available_tcp_port()
        try:
            docker.DockerClient().containers.get(self.container_name)
            self.is_initial_session = False
        except docker.errors.NotFound:
            self.is_initial_session = True
            logger.info(
                'No docker container found with the name %s. Will start a new session.',
                self.container_name,
            )
        if not config.persist_sandbox or self.is_initial_session:
            logger.info('Creating new Docker container')
            n_tries = 5
            while n_tries > 0:
                try:
                    self.restart_docker_container()
                    break
                except Exception as e:
                    logger.exception(
                        'Failed to start Docker container, retrying...', exc_info=False
                    )
                    n_tries -= 1
                    if n_tries == 0:
                        raise e
                    time.sleep(5)
            self.setup_user()
        else:
            self.container = self.docker_client.containers.get(self.container_name)
            logger.info('Using existing Docker container')

        super().__init__(
            'host.docker.internal', self._port, self._username, self._password
        )
        logger.info(
            f'DockerSSHBox is running as {self._username} user with USER_ID={config.sandbox_user_id} in the sandbox'
        )

    def setup_user(self):
        # Make users sudoers passwordless
        # TODO(sandbox): add this line in the Dockerfile for next minor version of docker image
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', r"echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"],
            workdir=config.workspace_mount_path_in_sandbox,
            environment=self._env,
        )
        if exit_code != 0:
            raise Exception(
                f'Failed to make all users passwordless sudoers in sandbox: {logs}'
            )

        # Check if the opendevin user exists
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', 'id -u opendevin'],
            workdir=config.workspace_mount_path_in_sandbox,
            environment=self._env,
        )
        if exit_code == 0:
            # User exists, delete it
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', 'userdel -r opendevin'],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to remove opendevin user in sandbox: {logs}')

        if config.ssh_username == 'opendevin':
            # Create the opendevin user
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f'useradd -rm -d /home/opendevin -s /bin/bash -g root -G sudo -u {config.sandbox_user_id} opendevin',
                ],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to create opendevin user in sandbox: {logs}')
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f"echo 'opendevin:{self._password}' | chpasswd",
                ],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to set password in sandbox: {logs}')

            # chown the home directory
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', 'chown opendevin:root /home/opendevin'],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(
                    f'Failed to chown home directory for opendevin in sandbox: {logs}'
                )
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f'chown opendevin:root {config.workspace_mount_path_in_sandbox}',
                ],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                # This is not a fatal error, just a warning
                logger.warning(
                    f'Failed to chown workspace directory for opendevin in sandbox: {logs}. But this should be fine if the {config.workspace_mount_path_in_sandbox=} is mounted by the app docker container.'
                )
        elif config.ssh_username == 'root':
            exit_code, logs = self.container.exec_run(
                # change password for root
                ['/bin/bash', '-c', f"echo 'root:{self._password}' | chpasswd"],
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to set password for root in sandbox: {logs}')
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', "echo 'opendevin-sandbox' > /etc/hostname"],
            workdir=config.workspace_mount_path_in_sandbox,
            environment=self._env,
        )

    def execute_in_background(self, cmd: str) -> Process:
        result = self.container.exec_run(
            self.get_exec_cmd(cmd),
            socket=True,
            workdir=config.workspace_mount_path_in_sandbox,
            environment=self._env,
        )
        result.output._sock.setblocking(0)
        pid = self.get_pid(cmd)
        bg_cmd = DockerProcess(self.cur_background_id, cmd, result, pid)
        self.background_commands[bg_cmd.pid] = bg_cmd
        self.cur_background_id += 1
        return bg_cmd

    def get_pid(self, cmd):
        exec_result = self.container.exec_run('ps aux', environment=self._env)
        processes = exec_result.output.decode('utf-8').splitlines()
        cmd = ' '.join(self.get_exec_cmd(cmd))

        for process in processes:
            if cmd in process:
                pid = process.split()[1]  # second column is the pid
                return pid
        return None

    def kill_background(self, id: int) -> Process:
        if id not in self.background_commands:
            raise SandboxInvalidBackgroundCommandError()
        bg_cmd = self.background_commands[id]
        if bg_cmd.pid is not None:
            self.container.exec_run(
                f'kill -9 {bg_cmd.pid}',
                workdir=config.workspace_mount_path_in_sandbox,
                environment=self._env,
            )
        assert isinstance(bg_cmd, DockerProcess)
        bg_cmd.result.output.close()
        self.background_commands.pop(id)
        return bg_cmd

    def start_docker_container(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            logger.info('Container status: %s', container.status)
            if container.status != 'running':
                container.start()
                logger.info('Container started')
            elapsed = 0
            while container.status != 'running':
                time.sleep(1)
                elapsed += 1
                if elapsed > self.timeout:
                    break
                container = self.docker_client.containers.get(self.container_name)
        except Exception:
            logger.exception('Failed to start container')

    def remove_docker_container(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            container.stop()
            logger.info('Container stopped')
            container.remove()
            logger.info('Container removed')
            elapsed = 0
            while container.status != 'exited':
                time.sleep(1)
                elapsed += 1
                if elapsed > self.timeout:
                    break
                container = self.docker_client.containers.get(self.container_name)
        except docker.errors.NotFound:
            pass

    def is_container_running(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            if container.status == 'running':
                self.container = container
                return True
            return False
        except docker.errors.NotFound:
            return False

    @property
    def volumes(self):
        mount_dir = config.workspace_mount_path
        logger.info(f'Mounting workspace directory: {mount_dir}')
        cache_dest = f'/home/{self._username}/.cache'
        if self._username == 'root':
            cache_dest = '/root/.cache'
        return {
            mount_dir: {'bind': config.workspace_mount_path_in_sandbox, 'mode': 'rw'},
            # pip cache reuse
            config.cache_dir: {
                'bind': cache_dest,
                'mode': 'rw',
            },
        }

    def restart_docker_container(self):
        try:
            self.remove_docker_container()
        except docker.errors.DockerException as ex:
            logger.exception('Failed to remove container', exc_info=False)
            raise ex

        try:
            network_kwargs: dict[str, str | dict[str, int]] = {}
            if config.use_host_network:
                network_kwargs['network_mode'] = 'host'
            else:
                # FIXME: This is a temporary workaround for Mac OS
                network_kwargs['ports'] = {f'{self._port}/tcp': self._port}
                logger.warning(
                    (
                        'Using port forwarding for Mac OS. '
                        'Server started by OpenDevin will not be accessible from the host machine at the moment. '
                        'See https://github.com/OpenDevin/OpenDevin/issues/897 for more information.'
                    )
                )

            # start the container
            logger.info(f'Mounting volumes: {self.volumes}')
            self.container = self.docker_client.containers.run(
                self.container_image,
                # allow root login
                command=f"/usr/sbin/sshd -D -p {self._port} -o 'PermitRootLogin=yes'",
                **network_kwargs,
                working_dir=config.workspace_mount_path_in_sandbox,
                name=self.container_name,
                detach=True,
                volumes=self.volumes,
            )
            logger.info('Container started')
        except Exception as ex:
            logger.exception('Failed to start container', exc_info=False)
            raise ex

        # wait for container to be ready
        elapsed = 0
        while self.container.status != 'running':
            if self.container.status == 'exited':
                logger.info('container exited')
                logger.info('container logs:')
                logger.info(self.container.logs())
                break
            time.sleep(1)
            elapsed += 1
            self.container = self.docker_client.containers.get(self.container_name)
            logger.info(
                f'waiting for container to start: {elapsed}, container status: {self.container.status}'
            )
            if elapsed > self.timeout:
                break
        if self.container.status != 'running':
            raise Exception('Failed to start container')

    # clean up the container, cannot do it in __del__ because the python interpreter is already shutting down
    def close(self):
        containers = self.docker_client.containers.list(all=True)
        for container in containers:
            try:
                if (
                    container.name.startswith(self.container_name)
                    and not config.persist_sandbox
                ):
                    # only remove the container we created
                    # otherwise all other containers with the same prefix will be removed
                    # which will mess up with parallel evaluation
                    container.remove(force=True)
            except docker.errors.NotFound:
                pass
        super().close()


if __name__ == '__main__':
    try:
        ssh_box = DockerSSHBox()
    except Exception as e:
        logger.exception('Failed to start Docker container: %s', e)
        sys.exit(1)

    logger.info(
        "Interactive Docker container started. Type 'exit' or use Ctrl+C to exit."
    )

    # Initialize required plugins
    ssh_box.init_plugins([AgentSkillsRequirement(), JupyterRequirement()])
    logger.info(
        '--- AgentSkills COMMAND DOCUMENTATION ---\n'
        f'{AgentSkillsRequirement().documentation}\n'
        '---'
    )

    bg_cmd = ssh_box.execute_in_background(
        "while true; do echo -n '.' && sleep 10; done"
    )

    sys.stdout.flush()
    try:
        while True:
            try:
                user_input = input('$ ')
            except EOFError:
                logger.info('Exiting...')
                break
            if user_input.lower() == 'exit':
                logger.info('Exiting...')
                break
            if user_input.lower() == 'kill':
                ssh_box.kill_background(bg_cmd.pid)
                logger.info('Background process killed')
                continue
            exit_code, output = ssh_box.execute(user_input)
            logger.info('exit code: %d', exit_code)
            logger.info(output)
            if bg_cmd.pid in ssh_box.background_commands:
                logs = ssh_box.read_logs(bg_cmd.pid)
                logger.info('background logs: %s', logs)
            sys.stdout.flush()
    except KeyboardInterrupt:
        logger.info('Exiting...')
    ssh_box.close()
